n=[2,3,5,6,3,2,5,6,7]
guess=int(input("Enter ur guess: "+str(n)+" Which number doesn't have a pair "))
res=0
for i in n:
    res^=i
print("Numbers:",n, "Odd one out",res, "Your guess",guess)
if res==guess:
    print("You got it right!")
else: 
    print("You got it wrong!")
    print("The right answer was",res)