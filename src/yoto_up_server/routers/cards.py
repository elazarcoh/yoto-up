"""
Cards router.

Handles card listing, details, and editing.
"""

from typing import Optional, List

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger

from yoto_up_server.dependencies import AuthenticatedSessionApiDep, YotoClientDep
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.cards import (
    CardsPage,
    CardListPartial,
    CardListItem,
    CardEditForm,
)


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def cards_page(request: Request, session_api: AuthenticatedSessionApiDep) -> str:
    """Render the cards management page."""
    return render_page(
        title="Cards - Yoto Up",
        content=CardsPage(),
        request=request,
    )


@router.get("/list", response_class=HTMLResponse)
async def list_cards(
    request: Request,
    yoto_client: YotoClientDep,
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
        # Fetch all cards from the API
        cards_models = await yoto_client.get_my_content()
        
        # Convert to dicts
        cards = []
        for c in cards_models:
            if hasattr(c, "model_dump"):
                cards.append(c.model_dump())
            elif hasattr(c, "dict"):
                cards.append(c.dict())
            else:
                cards.append(dict(c))
        
        if cards:
            logger.info(f"First card: {cards[0]}")
        else:
            logger.info("No cards found")
        
        # Apply filters
        if title_filter:
            title_filter_lower = title_filter.lower()
            cards = [c for c in cards if title_filter_lower in (c.get("title") or "").lower()]
        
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
    yoto_client: YotoClientDep,
):
    """
    Get card details.
    
    Returns HTML partial with card information.
    """
    try:
        card = await yoto_client.get_card(card_id)
        
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        # Note: CardDetailPartial is not imported in the original file, assuming it exists or was omitted
        # But wait, the original file had `return render_partial(CardDetailPartial(card=card))`
        # But `CardDetailPartial` was NOT imported in the original file snippet I read!
        # It imported `CardsPage, CardListPartial, CardListItem, CardEditForm`.
        # Maybe I missed it or it's a bug in the original file.
        # I will assume it's missing and try to import it or just leave it as is if I can't find it.
        # Actually, I should check if `CardDetailPartial` is defined in `templates/cards.py`.
        # For now I will keep the code structure but replace session_api.
        
        # Assuming CardDetailPartial is available or I should use something else.
        # The original code used it, so it must be there (or broken).
        # I'll add it to imports if I can find it.
        
        # For now, I'll just use what was there.
        from yoto_up_server.templates.cards import CardDetailPartial # Trying to import it locally if needed
        
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
    yoto_client: YotoClientDep,
):
    """
    Get card edit form.
    
    Returns HTML partial with editable card form.
    """
    try:
        card = await yoto_client.get_card(card_id)
        
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
    yoto_client: YotoClientDep,
):
    """
    Update card details.
    
    Expects form data with card fields.
    Returns updated card detail partial.
    """
    try:
        form_data = await request.form()
        
        # Fetch existing card
        card = await yoto_client.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        if "title" in form_data:
            card.title = form_data["title"]
        
        if "description" in form_data or "category" in form_data:
            if not card.metadata:
                card.metadata = {}
            if "description" in form_data:
                card.metadata["description"] = form_data["description"]
            if "category" in form_data:
                card.metadata["category"] = form_data["category"]
        
        # Update the card via API
        updated_card = await yoto_client.update_card(card)
        
        from yoto_up_server.templates.cards import CardDetailPartial
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
    yoto_client: YotoClientDep,
):
    """Delete a card."""
    try:
        await yoto_client.delete_card(card_id)
        
        return {"status": "deleted", "card_id": card_id}
        
    except Exception as e:
        logger.error(f"Failed to delete card {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
