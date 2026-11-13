def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

first = int(input("Enter Largest number : "))
second = int(input("Enter Smallest number : "))

print("LCM is : ", first * second // gcd(first, second))