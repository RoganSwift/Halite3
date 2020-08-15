import numpy as np

#TODO: Implement http://www.ressources-actuarielles.net/EXT/ISFA/1226.nsf/0/f84f7ac703bf5862c12576d8002f5259/$FILE/Jones98.pdf

def solve_quad(x_values, y_values):
    #TODO: Comments
    x_int = []
    for value in x_values:
        x_int.append([value**2, value, 1])
    x = np.array(x_int)
    y = np.transpose(np.array(y_values))

    a, b, c = np.dot(np.linalg.inv(x),y)

    return -b/(2*a)

x = [1,4,5]
y = [4,6,5]

print(str(solve_quad(x,y)))