-- =============================================================================
-- EcoCart | 00_create_user.sql
-- Run ONCE as SYS/SYSTEM connected to the pluggable database XEPDB1.
-- Creates the ECOCART schema used by every other script.
-- Skip this file if the ECOCART user already exists on your installation.
-- Usage (SQL*Plus / SQLcl):  sql sys/<pwd>@localhost:1521/XEPDB1 as sysdba @00_create_user.sql
-- =============================================================================
ALTER SESSION SET CONTAINER = XEPDB1;

DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM dba_users WHERE username = 'ECOCART';
  IF v_cnt = 0 THEN
    -- Local demo password is aman; it must match ECOCART_DB_PASSWORD in .env
    EXECUTE IMMEDIATE 'CREATE USER ecocart IDENTIFIED BY "aman" DEFAULT TABLESPACE users QUOTA UNLIMITED ON users';
  END IF;
END;
/

GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE SEQUENCE,
      CREATE PROCEDURE, CREATE TRIGGER, CREATE TYPE TO ecocart;

PROMPT ECOCART user ready. Now connect as ECOCART and run 01_schema.sql.
