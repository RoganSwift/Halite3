import numpy as np

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