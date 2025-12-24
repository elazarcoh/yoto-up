"""
Cards router.

Handles card listing, details, and editing.
"""

from typing import Optional, List

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger

from yoto_up_server.dependencies import AuthenticatedApiDep
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.cards import (
    CardsPage,
    CardListPartial,
    CardListItem,
    CardEditForm,
)


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def cards_page(request: Request, api_service: AuthenticatedApiDep) -> str:
    """Render the cards management page."""
    return render_page(
        title="Cards - Yoto Up",
        content=CardsPage(),
        request=request,
    )


@router.get("/list", response_class=HTMLResponse)
async def list_cards(
    request: Request,
    api_service: AuthenticatedApiDep,
    title_filter: Optional[str] = Query(None, description="Filter by title"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page_num: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> str:
    """
    List cards with optional filtering.
    
    Returns HTML partial for HTMX updates.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Fetch all cards from the API
        cards = api.get_library()
        
        # Apply filters
        if title_filter:
            title_filter_lower = title_filter.lower()
            cards = [c for c in cards if title_filter_lower in (c.get("title", "") or "").lower()]
        
        if category:
            cards = [c for c in cards if c.get("metadata", {}).get("category") == category]
        
        # Paginate
        total = len(cards)
        start = (page_num - 1) * page_size
        end = start + page_size
        paginated_cards = cards[start:end]
        
        return render_partial(
            CardListPartial(
                cards=paginated_cards,
                total=total,
                page=page_num,
                page_size=page_size,
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to list cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}", response_class=HTMLResponse)
async def get_card_detail(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
):
    """
    Get card details.
    
    Returns HTML partial with card information.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        card = api.get_card(card_id)
        
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        return render_partial(CardDetailPartial(card=card))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/edit", response_class=HTMLResponse)
async def edit_card_form(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
):
    """
    Get card edit form.
    
    Returns HTML partial with editable card form.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        card = api.get_card(card_id)
        
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        return render_partial(CardEditForm(card=card))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get card edit form for {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{card_id}", response_class=HTMLResponse)
async def update_card(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
):
    """
    Update card details.
    
    Expects form data with card fields.
    Returns updated card detail partial.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        form_data = await request.form()
        
        # Build update payload from form data
        update_data = {}
        
        if "title" in form_data:
            update_data["title"] = form_data["title"]
        
        if "description" in form_data:
            if "metadata" not in update_data:
                update_data["metadata"] = {}
            update_data["metadata"]["description"] = form_data["description"]
        
        if "category" in form_data:
            if "metadata" not in update_data:
                update_data["metadata"] = {}
            update_data["metadata"]["category"] = form_data["category"]
        
        # Update the card via API
        # Note: The actual API method may differ based on the yoto_api implementation
        updated_card = api.update_card_metadata(card_id, update_data)
        
        return render_partial(CardDetailPartial(card=updated_card))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{card_id}")
async def delete_card(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
):
    """Delete a card."""
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        api.delete_card(card_id)
        
        return {"status": "deleted", "card_id": card_id}
        
    except Exception as e:
        logger.error(f"Failed to delete card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
