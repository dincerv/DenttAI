# shared/types — Ortak Pydantic Modelleri
# Bu modeller birden fazla serviste kullanılacak temel şemalardır.
# Prompt-2 ve sonrasında her servis kendi app/schemas/ altında
# bu base modelleri extend edecektir.

# Örnek kullanım:
#   from shared.types.base import ClinicBase, DoctorBase
