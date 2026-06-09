import json
from fastapi.routing import APIRoute
from classroom_downloader.main import app

routes = []
for r in app.routes:                                  # ORDERED — registration order matters
    e = {"path": r.path, "name": getattr(r, "name", None),
         "methods": sorted(r.methods) if getattr(r, "methods", None) else []}
    if isinstance(r, APIRoute):
        e["response_model"] = getattr(r.response_model, "__name__", None) if r.response_model else None
        e["status_code"] = r.status_code
        e["include_in_schema"] = r.include_in_schema
    routes.append(e)

print(json.dumps({
    "routes": routes,                                 # order-sensitive list
    "last_route_path": app.routes[-1].path,           # MUST equal "/{full_path:path}"
    "openapi": app.openapi(),
}, indent=2))
