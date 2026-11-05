import csv, sys
from mirror.runtime import get_store

def main(path):
    s, n = get_store(), 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            n += s.add_settlement(row["provider"].strip().lower(), row["reference"].strip(),
                                  int(row["amount_minor"]), row["currency"].strip())
    print(f"imported {n} new settlements")

if __name__ == "__main__":
    main(sys.argv[1])
