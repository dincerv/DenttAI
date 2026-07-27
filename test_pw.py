from passlib.context import CryptContext
ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
h = "$2b$12$7WMfgr.ixhT.tjxZuEQKQ.JjccvdI07NRoj6o2rnhEuv2GN2q05Qy"
print("Hash length:", len(h))
print("Verify Admin1234:", ctx.verify("Admin1234", h))
print("New hash for Admin1234:", ctx.hash("Admin1234"))
