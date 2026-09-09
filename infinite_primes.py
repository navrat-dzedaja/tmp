#!/usr/bin/env python3
"""Nekonečný generátor a výpis prvočísel."""

from math import isqrt
from typing import Iterator


def generate_primes() -> Iterator[int]:
    """Generuje prvočísla donekonečna, vzestupně."""
    yield 2  # Jediné sudé prvočíslo vyřešíme zvlášť.

    candidate = 3
    while True:
        # Dělitelnost stačí testovat lichými čísly do odmocniny z kandidáta.
        is_prime = True
        for divisor in range(3, isqrt(candidate) + 1, 2):
            if candidate % divisor == 0:
                is_prime = False
                break

        if is_prime:
            yield candidate

        candidate += 2  # Přeskakujeme sudá čísla, ta prvočísla být nemohou.


def main() -> None:
    """Vypisuje nalezená prvočísla, dokud uživatel program neukončí."""
    count = 0
    try:
        for prime in generate_primes():
            count += 1
            print(f"{count}. prvočíslo: {prime}")
    except KeyboardInterrupt:
        print(f"\nProgram ukončen uživatelem. Nalezeno prvočísel: {count}")


if __name__ == "__main__":
    main()
