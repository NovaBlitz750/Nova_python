def display_switches(number):
    print("\nSMART SWITCH BIT MONITOR")
    print("Decimal Value:", number)
    print("Binary Value :", format(number, "08b"))

    print("\nSwitch Status:")

    for bit in range(7, -1, -1):
        if number & (1 << bit):
            print(f"Switch {bit}: ON")
        else:
            print(f"Switch {bit}: OFF")


def count_switches_on(number):
    total = 0

    for bit in range(8):
        if number & (1 << bit):
            total += 1

    return total


number = int(input("Enter a number from 0 to 255: "))

display_switches(number)

print("\nTotal switches ON:", count_switches_on(number))

print("\nQuick Checks:")
print("Is Switch 0 ON?", bool(number & (1 << 0)))
print("Is Switch 3 ON?", bool(number & (1 << 3)))
print("Is Switch 7 ON?", bool(number & (1 << 7)))