from mirror.store import Store

s = Store()
print("dialect:", s.engine.dialect.name)
print("payments:", s._one("SELECT COUNT(*) AS n FROM payments")["n"])
