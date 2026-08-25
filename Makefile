# Reproduce the study end to end. Every target is idempotent.
VENV := .venv/bin

.PHONY: help setup ingest spatial dbt-deps dbt-stage corridors dbt postgis-up postgis-corridors postgis-down analysis all clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  %-20s %s\n",$$1,$$2}'

setup:  ## create the venv and install the package
	uv venv && uv pip install -e ".[dev]"

ingest:  ## pull every source, reconciled, with receipts
	$(VENV)/python -m nycbike.ingest.crashes
	$(VENV)/python -m nycbike.ingest.bike_routes
	$(VENV)/python -m nycbike.ingest.exposure
	@echo "ACS needs a free Census API key in .env -- see src/nycbike/ingest/acs.py"

spatial:  ## assign crashes to street segments
	$(VENV)/python -m nycbike.spatial_join

# The corridor build sits inside the dbt DAG: it reads int_segment_treatment
# and writes the parquet that fct_corridor_year_panel reads. dbt cannot put a
# Python step in its graph, so the ordering lives here. Run dbt-stage first.
dbt-deps:  ## install dbt packages (dbt_utils) -- required on a fresh checkout
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/dbt deps

dbt-stage: dbt-deps  ## build only what the corridor step needs (staging + treatment history)
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/dbt run --select staging+ int_segment_treatment

corridors:  ## group segments into corridors (DuckDB/graph build) -- needs dbt-stage
	$(VENV)/python -m nycbike.corridors

dbt: dbt-deps  ## build and test the whole warehouse -- needs corridors
	cd dbt && DBT_PROFILES_DIR=. ../$(VENV)/dbt build

postgis-up:  ## start the PostGIS container
	docker run -d --name nycbike-postgis \
	  -e POSTGRES_PASSWORD=nycbike -e POSTGRES_USER=nycbike -e POSTGRES_DB=nycbike \
	  -p 25432:5432 postgis/postgis:16-3.4 || docker start nycbike-postgis
	@until docker exec nycbike-postgis pg_isready -U nycbike >/dev/null 2>&1; do sleep 1; done
	@docker exec nycbike-postgis psql -U nycbike -d nycbike -c "CREATE EXTENSION IF NOT EXISTS postgis;"

postgis-corridors:  ## build corridors in PostGIS and verify against the DuckDB build
	$(VENV)/python scripts/run_postgis_corridors.py

postgis-down:  ## stop and remove the container
	-docker rm -f nycbike-postgis

analysis:  ## staggered difference-in-differences
	$(VENV)/python analysis/did.py

all: ingest spatial dbt-stage corridors dbt analysis  ## the whole pipeline, in dependency order

clean:  ## remove derived data, keep raw pulls
	rm -f data/nycbike.duckdb data/interim/*.parquet
	rm -rf dbt/target
