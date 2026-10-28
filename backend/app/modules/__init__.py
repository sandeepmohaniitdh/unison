"""The twelve modules of the backend. Each one has:

- models.py: its tables (SQLAlchemy)
- schemas.py: request and response bodies (Pydantic)
- service.py: the business rules and database work
- router.py: the HTTP endpoints, which only check input and call the service
"""
