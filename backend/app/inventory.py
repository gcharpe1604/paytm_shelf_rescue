from .schemas import InventoryItem


def safe_surplus(item: InventoryItem) -> int:
    return max(
        0,
        item.on_hand
        - item.forecast_until_restock
        - item.safety_stock
        - item.reserved,
    )
