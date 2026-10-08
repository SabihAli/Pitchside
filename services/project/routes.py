from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from futbot_common.errors import AuthError
from futbot_common.responses import DataResponse
from services.project.db import get_db
from services.project.deps import content_hash, require_user_id
from services.project.ingestion_trigger import enqueue_ingestion
from services.project.models import Project, ProjectFile, ProjectMemory
from services.project.schemas import (
    CreateMemoryRequest,
    CreateProjectRequest,
    MemoryItemResponse,
    MemoryListResponse,
    ProjectContextResponse,
    ProjectFileResponse,
    ProjectResponse,
    UpdateFileStatusRequest,
)
from services.project.storage import get_storage

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_owned_project(
    db: AsyncSession, project_id: str, user_id: str
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise AuthError("NOT_FOUND", "Project not found.", 404)
    if project.user_id != user_id:
        raise AuthError("FORBIDDEN", "You do not have access to this project.", 403)
    return project


@router.post("", response_model=DataResponse[ProjectResponse], status_code=201)
async def create_project(
    body: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    project = Project(user_id=user_id, name=body.name, description=body.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return DataResponse(
        data=ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
        )
    )


@router.get("", response_model=DataResponse[list[ProjectResponse]])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return DataResponse(
        data=[
            ProjectResponse(
                id=p.id, name=p.name, description=p.description, created_at=p.created_at
            )
            for p in projects
        ]
    )


@router.get("/{project_id}", response_model=DataResponse[ProjectResponse])
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    project = await _get_owned_project(db, project_id, user_id)
    return DataResponse(
        data=ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
        )
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    project = await _get_owned_project(db, project_id, user_id)
    await db.delete(project)
    await db.commit()
    return Response(status_code=204)


@router.post(
    "/{project_id}/files",
    response_model=DataResponse[ProjectFileResponse],
    status_code=201,
)
async def upload_file(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    project = await _get_owned_project(db, project_id, user_id)
    data = await file.read()
    digest = content_hash(data)
    storage_key = f"projects/{project_id}/{digest}/{file.filename}"
    storage = get_storage()
    storage.put(storage_key, data, file.content_type or "application/octet-stream")

    row = ProjectFile(
        project_id=project.id,
        filename=file.filename or "upload",
        content_hash=digest,
        storage_key=storage_key,
        status="pending",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    background_tasks.add_task(
        enqueue_ingestion,
        project_id=project.id,
        file_id=row.id,
        filename=row.filename,
        storage_key=row.storage_key,
        content_hash=row.content_hash,
    )
    return DataResponse(
        data=ProjectFileResponse(
            id=row.id,
            filename=row.filename,
            content_hash=row.content_hash,
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )
    )


@router.get("/{project_id}/files", response_model=DataResponse[list[ProjectFileResponse]])
async def list_files(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    await _get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at.desc())
    )
    files = result.scalars().all()
    return DataResponse(
        data=[
            ProjectFileResponse(
                id=f.id,
                filename=f.filename,
                content_hash=f.content_hash,
                status=f.status,
                error_message=f.error_message,
                created_at=f.created_at,
            )
            for f in files
        ]
    )


@router.patch(
    "/{project_id}/files/{file_id}/status",
    response_model=DataResponse[ProjectFileResponse],
)
async def update_file_status(
    project_id: str,
    file_id: str,
    body: UpdateFileStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise AuthError("NOT_FOUND", "File not found.", 404)

    row.status = body.status
    row.error_message = body.error_message
    await db.commit()
    await db.refresh(row)
    return DataResponse(
        data=ProjectFileResponse(
            id=row.id,
            filename=row.filename,
            content_hash=row.content_hash,
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )
    )


@router.post(
    "/{project_id}/memory",
    response_model=DataResponse[MemoryItemResponse],
    status_code=201,
)
async def add_memory(
    project_id: str,
    body: CreateMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    project = await _get_owned_project(db, project_id, user_id)
    row = ProjectMemory(
        project_id=project.id,
        memory_type=body.memory_type,
        content=body.content,
        source_chat_id=body.source_chat_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return DataResponse(
        data=MemoryItemResponse(
            id=row.id,
            memory_type=row.memory_type,
            content=row.content,
            source_chat_id=row.source_chat_id,
            created_at=row.created_at,
        )
    )


@router.get("/{project_id}/memory", response_model=DataResponse[MemoryListResponse])
async def list_memory(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    await _get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(ProjectMemory)
        .where(ProjectMemory.project_id == project_id)
        .order_by(ProjectMemory.created_at.desc())
    )
    items = result.scalars().all()
    return DataResponse(
        data=MemoryListResponse(
            items=[
                MemoryItemResponse(
                    id=m.id,
                    memory_type=m.memory_type,
                    content=m.content,
                    source_chat_id=m.source_chat_id,
                    created_at=m.created_at,
                )
                for m in items
            ]
        )
    )


@router.get("/{project_id}/context", response_model=DataResponse[ProjectContextResponse])
async def project_context(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_user_id),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.files), selectinload(Project.memory))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise AuthError("NOT_FOUND", "Project not found.", 404)
    if project.user_id != user_id:
        raise AuthError("FORBIDDEN", "You do not have access to this project.", 403)

    return DataResponse(
        data=ProjectContextResponse(
            project=ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                created_at=project.created_at,
            ),
            files=[
                ProjectFileResponse(
                    id=f.id,
                    filename=f.filename,
                    content_hash=f.content_hash,
                    status=f.status,
                    error_message=f.error_message,
                    created_at=f.created_at,
                )
                for f in project.files
            ],
            memory=[
                MemoryItemResponse(
                    id=m.id,
                    memory_type=m.memory_type,
                    content=m.content,
                    source_chat_id=m.source_chat_id,
                    created_at=m.created_at,
                )
                for m in project.memory
            ],
        )
    )
