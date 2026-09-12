from typing import Literal, Protocol
from uuid import uuid4

from .demo_data import DemoStore
from .schemas import PaymentRecord, Reservation


class PaymentProvider(Protocol):
    def create_payment(
        self,
        buyer_id: str,
        seller_id: str,
        amount: int,
        reference: str,
    ) -> PaymentRecord: ...


class MockPaymentProvider:
    def __init__(
        self, force_status: Literal["success", "failed"] = "success"
    ) -> None:
        self.force_status = force_status

    def create_payment(
        self,
        buyer_id: str,
        seller_id: str,
        amount: int,
        reference: str,
    ) -> PaymentRecord:
        payment_id = str(uuid4())
        return PaymentRecord(
            payment_id=payment_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            amount=amount,
            reference=reference,
            status=self.force_status,
            payment_url=(
                f"http://localhost:8000/mock-payments/{payment_id}"
                if self.force_status == "success"
                else None
            ),
        )


def execute_rescue(
    store: DemoStore,
    payment_provider: PaymentProvider,
    reservation_id: str,
) -> tuple[Reservation, PaymentRecord]:
    reservation = store.get_reservation(reservation_id)
    if reservation.status != "reserved":
        raise ValueError("Rescue execution requires a reserved reservation")

    try:
        payment = payment_provider.create_payment(
            buyer_id=reservation.buyer_id,
            seller_id=reservation.supplier_id,
            amount=reservation.total_amount,
            reference=reservation.reservation_id,
        )
    except Exception:
        store.release_reservation(reservation_id)
        raise

    final_reservation = (
        store.commit_reservation(reservation_id)
        if payment.status == "success"
        else store.release_reservation(reservation_id)
    )
    return final_reservation, payment
