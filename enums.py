from enum import Enum
import strawberry


@strawberry.enum
class CertificateStatusType(Enum):
    PENDING_CC = "pending_cc"
    PENDING_SLO = "pending_slo"
    APPROVED = "approved"
