from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.core.deps import DB, ClockDep, CurrentUser, StorageDep
from app.core.downloads import FILE_RESPONSE, file_download
from app.core.openapi import errors
from app.core.pagination import Page, Pagination
from app.modules.resources import service
from app.modules.resources.schemas import LinkIn, PublishIn, ResourceOut, ResourceUpdate

router = APIRouter(tags=["resources"])


@router.get(
    "/courses/{course_id}/resources",
    response_model=Page[ResourceOut],
    summary="A course's resources",
    responses=errors(401, 403, 404),
)
def list_resources(
    course_id: int, db: DB, user: CurrentUser, page: Pagination, status: Literal["draft", "published"] | None = None
):
    """Students see published resources; teachers also see drafts."""
    return service.list_for_course(db, user, course_id, page, status)


@router.post(
    "/courses/{course_id}/resources/files",
    response_model=ResourceOut,
    status_code=201,
    summary="Upload a file resource (draft)",
    responses=errors(401, 403, 404, 409, 413),
)
def create_file_resource(
    course_id: int,
    db: DB,
    storage: StorageDep,
    clock: ClockDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="PDF, Word, PowerPoint, Excel, text, PNG, JPEG or ZIP; up to 25 MB.")],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    description: Annotated[str | None, Form(max_length=5000)] = None,
):
    return service.add_file(db, user, course_id, title, description, file.file, file.filename, storage, clock)


@router.post(
    "/courses/{course_id}/resources/links",
    response_model=ResourceOut,
    status_code=201,
    summary="Add a link resource (draft)",
    responses=errors(401, 403, 404, 409),
)
def create_link_resource(course_id: int, body: LinkIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.add_link(db, user, course_id, body.title, body.description, str(body.url), clock)


@router.post(
    "/courses/{course_id}/resource-publications",
    response_model=list[ResourceOut],
    status_code=201,
    summary="Publish one or several resources",
    responses=errors(401, 403, 404, 409),
)
def create_resource_publication(course_id: int, body: PublishIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Several resources published together give one notification. Emails are
    bundled per student over 10 minutes."""
    return service.publish(db, user, course_id, body.resource_ids, body.notify, clock)


@router.patch(
    "/resources/{resource_id}",
    response_model=ResourceOut,
    summary="Edit a resource",
    responses=errors(401, 403, 404, 409),
)
def update_resource(resource_id: int, body: ResourceUpdate, db: DB, user: CurrentUser):
    return service.update(db, user, resource_id, body.model_dump(exclude_unset=True))


@router.delete(
    "/resources/{resource_id}", status_code=204, summary="Delete a resource", responses=errors(401, 403, 404, 409)
)
def delete_resource(resource_id: int, db: DB, storage: StorageDep, user: CurrentUser):
    service.remove(db, user, resource_id, storage)
    return Response(status_code=204)


@router.get(
    "/resources/{resource_id}/content",
    summary="Download a file resource's content",
    responses={**FILE_RESPONSE, **errors(401, 403, 404, 409)},
)
def get_resource_content(resource_id: int, db: DB, storage: StorageDep, user: CurrentUser):
    path, name, mime = service.download(db, user, resource_id, storage)
    return file_download(path, name, mime)
