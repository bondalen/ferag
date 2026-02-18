#!/bin/bash
set -e

# Скрипт для создания двух БД при инициализации PostgreSQL
# Использование: POSTGRES_MULTIPLE_DATABASES=db1,db2

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE ferag_app;
    CREATE DATABASE ferag_projections;
    GRANT ALL PRIVILEGES ON DATABASE ferag_app TO ferag;
    GRANT ALL PRIVILEGES ON DATABASE ferag_projections TO ferag;
EOSQL
