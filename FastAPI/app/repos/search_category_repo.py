from sqlalchemy.orm import Session

from app.models.search_category import SearchCategory
from app.models.user import User
from app.core.security import generate_id


def create(db: Session, slug: str, display_name: str) -> SearchCategory:
    cat = SearchCategory(
        id=generate_id(),
        slug=slug,
        display_name=display_name,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def get_all(db: Session) -> list[SearchCategory]:
    return db.query(SearchCategory).order_by(SearchCategory.slug).all()


def get_categories_with_active_users(db: Session) -> list[SearchCategory]:
    """
    Return categories that have at least one active user assigned.
    Use this to avoid scraping categories nobody uses.
    """
    return (
        db.query(SearchCategory)
        .join(User, User.search_category_id == SearchCategory.id)
        .filter(User.is_active == True)
        .distinct()
        .order_by(SearchCategory.slug)
        .all()
    )


def get_by_slug(db: Session, slug: str) -> SearchCategory | None:
    return db.query(SearchCategory).filter(SearchCategory.slug == slug).first()


def get_by_id(db: Session, category_id: str) -> SearchCategory | None:
    return db.query(SearchCategory).filter(SearchCategory.id == category_id).first()


def seed_default_categories(db: Session) -> tuple[list[SearchCategory], int]:
    """
    Seed canonical search categories if table is empty.
    Returns (list of categories, number_created). number_created is 0 if table already had rows.
    """
    existing = get_all(db)
    if existing:
        return existing, 0
    defaults = [
        ("software_engineer", "Software Engineer"),
        ("data_scientist", "Data Scientist"),
        ("mechanical_engineer", "Mechanical Engineer"),
        ("product_manager", "Product Manager"),
    ]
    created = []
    for slug, display_name in defaults:
        cat = create(db, slug, display_name)
        created.append(cat)
    return created, len(created)
