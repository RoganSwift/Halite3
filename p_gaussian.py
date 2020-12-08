import numpy as np
from scipy.linalg import cho_factor, cho_solve
import matplotlib.pyplot as plt

def kernel_sqexp (a, s, r):
    '''return a * np.exp (-0.5 * (r / s)**2)'''
    return a * np.exp (-0.5 * (r / s)**2)

def gaussian_process_covariance_matrix (kernel, x, noise_scale_vector):
    '''Apply the kernel to the matrix of separations (r[i,j] = x[j] - x[i]) and add noise_scale_vector along the diagonal.'''
    # "kernel" is a one-parameter GP kernel function; we can
    # derive it from (e.g.) sqexp_kernel using a Python
    # lambda expression.
    
    # Matrix of separations: r[i,j] = x[j] - x[i]
    r = x[np.newaxis,:] - x[:,np.newaxis]
    return kernel (r) + np.diag (noise_scale_vector)

def sample_from_covariance_matrix (covariance_matrix):
    '''Create random curve obeying the covariance matrix.'''
    # random_vector is a random vector
    random_vector = np.random.normal (size=covariance_matrix.shape[0])

    # our random_vector has mean 0 and no covariance (covariance matrix = identity matrix)
    # This simplifies the equation C_s = A * C_r * A.T to C_s = A * A.T
    # We want a C_s that is our covariance matrix. The solution for C = A * A.T is A = cholesky(C)
    # A is what enforces our covariance matrix on the random vector, making it a random continuous curve
    return np.dot (np.linalg.cholesky (covariance_matrix), random_vector)

def krige (data_xs, data_ys, covariance_matrix, kernel, interpolant_xs):
    # covariance_array  is covariance between our actual measurements (rows) and each of the points we're checking (columns)
    # covariance_matrix is covariance between the points we're checking and each other
    covariance_array = kernel (data_xs[:,np.newaxis] - interpolant_xs[np.newaxis,:])
    
    # weight_array is, for each point we're checking, the weighting for each actual measurement's y value
    inverse_covariance_matrix = np.linalg.inv (covariance_matrix)
    weight_array = np.dot (inverse_covariance_matrix, covariance_array)
    
    # interpolant_ys is our prediction for each interpolant_x
    interpolant_ys = np.dot (weight_array.T, data_ys)

    # interpolant_variance is our prediction of variance for each interpolant_x
    auto_covariance = kernel (0)
    interpolant_variance = auto_covariance - np.dot (covariance_array.T, weight_array)

    return interpolant_ys, interpolant_variance

def show_me_sample_functions():
    x = np.linspace (0, 10, 300)
    kern = lambda r: kernel_sqexp (1., 1., r)
    cov = gaussian_process_covariance_matrix (kern, x, 1e-9 * np.ones_like (x))

    for _ in range (10):
        # ten times, plot a randomly-generated curve
        plt.plot (x, sample_from_covariance_matrix (cov))
    plt.show()

def show_me_prediction_ability():
    # The underlying signal -- there's a trend described by a Gaussian
    # process, but no measurement error.
    true_x = np.linspace (0, 10, 300)
    true_kern = lambda r: kernel_sqexp (1., 1., r)
    true_cov = gaussian_process_covariance_matrix (true_kern, true_x, 1e-9 * np.ones_like (true_x))
    true_y = sample_from_covariance_matrix (true_cov)

    # The data -- samples of the signal, plus noise.
    w = np.asarray ([30, 75, 150, 155, 210, 240, 255])
    data_x = true_x[w]
    data_u = 0.02 * np.ones_like (data_x)
    data_y = true_y[w] + np.random.normal (scale=data_u)
    data_cov = gaussian_process_covariance_matrix (true_kern, data_x, data_u)

    # Our best guess of the underlying signal given the noisy measurements.
    interp_x = true_x
    interp_y, interp_cov = krige (data_x, data_y, data_cov,
                                  true_kern, interp_x)
    interp_u = np.sqrt (np.diag (interp_cov))

    # identify the highest predicted point
    interp_max_pos = np.argmax(interp_y + interp_u)

    plt.plot(data_x, data_y, "o", label='Data')
    plt.plot(true_x, true_y, label='True')
    plt.plot(true_x[interp_max_pos], true_y[interp_max_pos], "o", label="highest")
    plt.plot(interp_x, interp_y, label=u'GP interp, 1σ') 
    plt.plot(interp_x, interp_y + interp_u, linestyle="--")
    plt.plot(interp_x, interp_y - interp_u, linestyle="--")
    plt.show()

show_me_prediction_ability()