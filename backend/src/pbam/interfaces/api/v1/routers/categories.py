"""Categories router: CRUD + tree."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from pbam.application.finance.commands import NotFoundError
from pbam.interfaces.api.v1.schemas.finance import CategoryCreate, CategoryResponse, CategoryUpdate
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/categories", tags=["categories"])


def _build_tree(categories) -> list[CategoryResponse]:
    """Convert flat list → nested tree."""
    by_id = {}
    roots = []
    for cat in categories:
        node = CategoryResponse(
            id=cat.id, name=cat.name, category_type=str(cat.category_type),
            parent_id=cat.parent_id, color=cat.color, icon=cat.icon,
            sort_order=cat.sort_order, is_system=cat.is_system, children=[],
        )
        by_id[cat.id] = node

    for cat in categories:
        node = by_id[cat.id]
        if cat.parent_id and cat.parent_id in by_id:
            by_id[cat.parent_id].children.append(node)
        else:
            roots.append(node)

    return sorted(roots, key=lambda n: n.sort_order)


@router.get("", response_model=list[CategoryResponse])
async def list_categories(facade: Facade, current_user_id: CurrentUserId):
    cats = await facade.list_categories(current_user_id)
    return _build_tree(cats)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(body: CategoryCreate, facade: Facade, current_user_id: CurrentUserId):
    cat = await facade.create_category(
        current_user_id,
        name=body.name,
        category_type=body.category_type,
        parent_id=body.parent_id,
        color=body.color,
        icon=body.icon,
        sort_order=body.sort_order,
    )
    return CategoryResponse(
        id=cat.id, name=cat.name, category_type=str(cat.category_type),
        parent_id=cat.parent_id, color=cat.color, icon=cat.icon,
        sort_order=cat.sort_order, is_system=cat.is_system, children=[],
    )


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID, body: CategoryUpdate, facade: Facade, current_user_id: CurrentUserId
):
    try:
        cat = await facade.update_category(
            category_id, current_user_id, **body.model_dump(exclude_none=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryResponse(
        id=cat.id, name=cat.name, category_type=str(cat.category_type),
        parent_id=cat.parent_id, color=cat.color, icon=cat.icon,
        sort_order=cat.sort_order, is_system=cat.is_system, children=[],
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    try:
        await facade.delete_category(category_id, current_user_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
