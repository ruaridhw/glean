"""Dev-only retailer ground truth for the dietary audits. Never imported by `src/glean`."""

from .classify import classify
from .models import AllergenFacts, Product, ProductRef

__all__ = ["AllergenFacts", "Product", "ProductRef", "classify"]
