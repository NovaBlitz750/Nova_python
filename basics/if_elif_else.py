weather=input("How is the weather today? ").strip().capitalize()
if weather=="Sunny":
    print("It is hot outside")
elif weather=="Cloudy":
    print("It is about to rain")
elif weather=="Humid":
    print("It is humid outside")
else:
    print("It is snowing")