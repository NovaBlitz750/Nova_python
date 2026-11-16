prime_numbers=[]
for no in range (100):
     
    if no<=1:
        pass
    else: 
        for i in range(2,no):
            if no%i==0:
                pass
        else:
                prime_numbers.append(no)
print("All 2 digit prime numbers are: ",prime_numbers)