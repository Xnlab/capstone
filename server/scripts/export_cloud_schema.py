"""Print reviewed initial schema + fictional-free built-in definitions, not user data.

Run with DATABASE_SCHEMA=capstone. Apply only to a new, empty cloud project.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from app.core.database import Base
from app import models
from app.builtin_templates import BUILTIN_TEMPLATES

assert Base.metadata.schema == "capstone"
statements = []
for table in Base.metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=postgresql.dialect())) + ";")
    for index in table.indexes:
        statements.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ";")
    statements.append(f"ALTER TABLE capstone.{table.name} ENABLE ROW LEVEL SECURITY;")
    statements.append(f"CREATE POLICY backend_access ON capstone.{table.name} FOR ALL TO capstone_api USING (true) WITH CHECK (true);")
statements += ["GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA capstone TO capstone_api;",
               "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA capstone TO capstone_api;"]

def quote(value):
    return "'" + str(value).replace("'", "''") + "'"

for t in BUILTIN_TEMPLATES:
    values = ["NULL", "'builtin'", quote(t["key"]), quote(t["name"]), quote(t["category"]),
              quote(t["description"]), quote(json.dumps(t["aliases"], ensure_ascii=False)),
              quote(json.dumps(t["definition"], ensure_ascii=False)), "'[]'", "'ready'", "CURRENT_TIMESTAMP"]
    statements.append("INSERT INTO capstone.templates (owner_id,kind,key,name,category,description,aliases,definition,fields,status,created_at) VALUES (" + ",".join(values) + ");")
print("\n".join(statements))
