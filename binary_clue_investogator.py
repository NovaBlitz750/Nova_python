print("Binary Clue Investogator")
res=0
l1=[5, 2, 6, 2, 5, 8, 6]
input("XOR with 0 keeps the number. Press Enter ")
print(" 5 ^ 0 = ",5^0)

input("XOR with itself gives 0. Press Enter ")
print(" 5 ^ 5 = ", 5^5)
n=int(input("Enter a number "))
print("3 ^",n,"^ 3 = ",3^n^3)
print(" ")
print("Numbers = " ,str(l1))
odd=int(input("Which number doesn't have a pair in the above list? "))

for i in l1:
    res^=i
print("Numbers:",l1, "Odd one out",res, "Your guess",odd)
if res==odd:
    print("You got it right!")
else: 
    print("You got it wrong!")
    print("The right answer was",res)