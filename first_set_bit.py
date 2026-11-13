x=int(input("Enter a no "))
if x==0:
    print("There is not set bit")
else:
    p=1
    while x>0:
        if x&1:
            print("The positon is",p)
            break
        x=x>>1
        p+=1