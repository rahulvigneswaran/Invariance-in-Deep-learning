# Libraries Import
import os
import pickle
from datetime import datetime
import argparse
import matplotlib.pyplot as plt
import autograd.numpy as np
import sys
import shutil
import math
import random
import pickle

import data
import model
from scipy.linalg import subspace_angles
import math

from tqdm import tqdm

import torch
from pyfiglet import Figlet


os.system('clear')
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

print("===============================================================================================")
f = Figlet(font='thin')
print(f.renderText('Invariance Baseline'))
print(":::: Code by Adepu Ravi Shankar & Rahul-Vigneswaran K 2019 ::::")
print("===============================================================================================\n")


# Initialize Variables

prev_hess = 0
prev_eigval = 0
prev_eigvec = 0
initial_model = []

parser = argparse.ArgumentParser()
    # Hessian
parser.add_argument('--top', type=int, default= 100,
                    help='Dimension of the top eigenspace')
parser.add_argument('--suffix', type=str, default='new',
                    help='suffix to save npy array')
parser.add_argument('--freq', type=int, default='1',
                    help='freq of Hess calculation')


# Data Generation
parser.add_argument('--data-type', type=str, choices=['blob', 'circle', 'moon'], default='blob',
                    help='Type of random data generation pattern.')
parser.add_argument('--num-samples', type=int, default=1000,
                    help='Number of training samples')
parser.add_argument('--input-dim', type=int, default=5,
                    help='Dimension of the input space')
parser.add_argument('--num-classes', type=int, default=2,
                    help='Number of classes in generated data. '
                         'Taken into account only by classifiers and data generators that support multi-class')
parser.add_argument('--cov-factor', type=float, default=1.,
                    help='Multiplier for the covariance of the data')
parser.add_argument('--data-seed', type=int, default=None,
                    help='Seed for random number generation of data generators')

# Model
parser.add_argument('--classifier', type=str, choices=['logreg', 'fullconn'], default='fullconn',
                    help='Type of classifier. Logistic Regression, Fully-Connected NN.')
parser.add_argument('--layer-sizes', nargs='*', type=int, default=[10, 5],
                    help='Number of units in hidden layers. '
                         'First layer will have --input-dim units. Last layer will have --num-classes units.')

# Training
parser.add_argument('--batch-size', type=int, default=0,
                    help='Number of samples in a training batch. '
                         '0 means whole dataset')
parser.add_argument('--learning-rate', type=float, default=0.01,
                    help='Learning rate')
parser.add_argument('--stopping-grad-norm', type=float, default=1e-4,
                    help='Stop training if grad_norm becomes smaller than this threshold')
parser.add_argument('--max-iterations', type=int, default=100,
                    help='Cancel training after maximum number of iteration steps')

# Results
parser.add_argument('--hessian-calc-period', type=int, default=1,
                    help='Calculate hessian at every N iteration. '
                         '0 means do not calculate at intermediate iterations.')
parser.add_argument('--results-folder', type=str, default='/home/ravi/eclipse-workspace/saguant/hessian-for-basicDL/hessianexps/results',
                    help='Folder in which to put all results folders')
parser.add_argument('--experiment-folder', type=str, default='defaults',
                    help='Folder in which to write results files')

# Hessian analysis
parser.add_argument('--top-evals', type=int, default=100,
                    help='Find top k evals')
parser.add_argument('--bottom-evals', type=int, default=0,
                    help='Find bottom k evals')

args = parser.parse_args()
#args.layer_sizes = np.array(args.layer_sizes)

def yes_or_no() :
    while True:
        yes = {'yes','y', 'ye', ''}
        no = {'no','n'}

        choice = raw_input("Do you want me to delete the directory? (y/n) \n\n").lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            sys.stdout.write("\nPlease respond with 'yes' or 'no' \n\n")

def yes_or_no_image():
    while True:
        yes = {'yes', 'y', 'ye', ''}
        no = {'no', 'n'}

        choice = raw_input(
            "Do you want to see the plot? (y/n) \n\n").lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            sys.stdout.write("\nPlease respond with 'yes' or 'no' \n\n")


args.results_folder = os.getcwd() + '/' +'results/' + 'baseline/' +'B_size-'+str(args.batch_size)+'-Arch-'+str(args.input_dim)+str(args.layer_sizes)+'-iters-'+str(args.max_iterations)+'-data-'+str(args.data_type)+'-hess_freq-'+str(args.hessian_calc_period)+'-top-'+str(args.top)+'--freq-'+str(args.freq)+'--iter-'+str(args.max_iterations)
if not os.path.exists(args.results_folder):
    os.mkdir(args.results_folder)
else:    
    print("\nDirectory already exists !!\n")
    a1 = yes_or_no()
    if a1 == True :
         shutil.rmtree(args.results_folder, ignore_errors=True)         # Prompt to delete directory if it already exists
         print("====> Directory Deleted")
         os.mkdir(args.results_folder)
         print("====> Directory recreated\n")
         print("===============================================================================================\n")


    else:
        print ("Directory Already exists and was not opted for deletion.\n\n")
        sys.exit()
    
if args.classifier == 'logreg' and args.data_type == 'blob' and args.num_classes != 2:
    raise Exception('LogReg for more than 2 classes is not implemented yet.')


def main():
    inputs_train, targets_train, inputs_test, targets_test = data.generate_data(args)
    results = {
        'inputs_train': inputs_train,
        'targets_train': targets_train,
        'inputs_test': inputs_test,
        'targets_test': targets_test
    }
    
    mdl = model.create_model(args, inputs_train, targets_train)     # Actual Model that is being observed
    mdl_test = model.create_model(args, inputs_train, targets_train)    # Dummy Model for calculating gradient
    train_model(args, mdl, mdl_test, results)


def train_model(args, mdl, mdl_test, results):
    coeff = []
    ang_sb=[]
    ang_np=[]
    p_angles = []
    all_w=[]
    results['args'] = args
    loss=[]

    init_loss = mdl.loss(mdl.params_flat)
    init_grad_norm = np.linalg.norm(mdl.gradient(mdl.params_flat))
    print("\n===============================================================================================\n")

    print('Initial loss: {}, norm grad: {}\n'.format(init_loss, init_grad_norm))
    results['init_full_loss'] = init_loss
    results['init_full_grad_norm'] = init_grad_norm

    results['history1'] = []
    results['history1_columns'] = ['iter_no', 'batch_loss', 'batch_grad_norm', 'batch_param_norm']
    results['history2'] = []
    results['history2_columns'] = ['full_hessian', 'full_hessian_evals']

    for iter_no in tqdm(range(args.max_iterations), desc="Training Progress", dynamic_ncols=True):
        inputs, targets = get_batch_samples(iter_no, args, mdl)
        batch_loss = mdl.loss(mdl.params_flat, inputs, targets)
        batch_grad = mdl.gradient(mdl.params_flat, inputs, targets)
        batch_grad_norm = np.linalg.norm(batch_grad)
        batch_param_norm = np.linalg.norm(mdl.params_flat)

        if iter_no % args.freq == 0:

            # calculating hessian
            hess = mdl.hessian(mdl.params_flat)                 # Calculating Hessian
            hess = torch.tensor(hess).float()                   # Converting the Hessian to Tensor
            eigenvalues, eigenvec = torch.symeig(hess,eigenvectors=True)    # Extracting the eigenvalues and Eigen Vectors from the Calculated Hessian
            
            if iter_no == 0:
                prev_hess = hess
                prev_eigval = eigenvalues
                prev_eigvec = eigenvec
            
            top = args.top      # This decides how many top eigenvectors are considered
            dom = eigenvec[:,-top:]     # |The reason for negative top :: torch.symeig outputs eigen vectors in the increasing order and as a result |
                                        # |                               the top (maximum) eigenvectors will be atlast.                             |
            dom = dom.float()
            alpha=torch.rand(top)       # A random vector which is of the dim of variable "top" is being initialized

            # Finding the top vector
            vec=(alpha*dom.float()).sum(1)          # Representing alpha onto dominant eigen vector
            vec=vec/torch.sqrt((vec*vec).sum())     # Normalization of top vector
#            vec = vec*5

            # Finding gradient at top vec using Dummy network.
            mdl_test.params_flat = np.array(vec)
            
            
            batch_grad_mdl_test = mdl_test.gradient(mdl_test.params_flat, inputs, targets)
            mdl_test.params_flat -= batch_grad_mdl_test * args.learning_rate

            # Find coeff and append. But why do we need to find the coeffs ?                                              
            c =  torch.mv(hess.transpose(0,1), torch.tensor(mdl_test.params_flat).float())
            if np.size(coeff) == 0:
                coeff = c.detach().cpu().numpy()
                coeff = np.expand_dims(coeff, axis=0)
            else:
                coeff = np.concatenate((coeff,np.expand_dims(c.detach().cpu().numpy(),axis=0)),0) 

#	Statistics of subspaces, (1) Angle between top subpaces
            eigenvalues_prev, eigenvec_prev = torch.symeig(prev_hess, eigenvectors = True)
            dom_prev = eigenvec_prev[:,-top:]           # Is it not the same as the variable "dom" that was calculated earlier ?
            # calculation 1 norm, which is nothing but angle between subspaces
            ang=np.linalg.norm(torch.mm(dom_prev, dom.transpose(0,1)).numpy(),1)
            ang_sb.append(ang)
            ang = np.rad2deg(subspace_angles(dom_prev, dom))
            ang_np.append(ang)
#    Calculating principal angles
            u,s,v =torch.svd(torch.mm(dom.transpose(0, 1), dom_prev))
            #    Output in radians
            s = torch.acos(torch.clamp(s,min=-1,max=1))
            s = s*180/math.pi
#    Attach 's' to p_angles
            if np.size(p_angles) == 0:
                p_angles = s.detach().cpu().numpy()
                p_angles = np.expand_dims(p_angles, axis=0)
            else:
                p_angles = np.concatenate((p_angles,np.expand_dims(s.detach().cpu().numpy(),axis=0)),0) 
            prev_hess = hess
            prev_eigval = eigenvalues
            prev_eigvec = eigenvec

#    saving weights in all iterations
        if batch_grad_norm <= args.stopping_grad_norm:
            break
        mdl.params_flat -= batch_grad * args.learning_rate
        #print(mdl.params_flat)
        all_w.append(np.power(math.e,mdl.params_flat))
       # print('{:06d} {} loss: {:.8f}, norm grad: {:.8f}'.format(iter_no, datetime.now(), batch_loss, batch_grad_norm))
        loss.append(batch_loss)
    final_loss = mdl.loss(mdl.params_flat)
    final_grad_norm = np.linalg.norm(mdl.gradient(mdl.params_flat))
    print('\nFinal loss: {}, norm grad: {}'.format(final_loss, final_grad_norm))
    args.suffix=args.results_folder+'/coeff.npy'
    np.save(args.suffix,coeff)
    args.suffix=args.results_folder+'/ang_sb.npy'
    np.save(args.suffix,ang_sb)
    args.suffix=args.results_folder+'/ang_np.npy'
    np.save(args.suffix,ang_np)   
    args.suffix=args.results_folder+'/p_angles.npy'
    np.save(args.suffix,p_angles)   
    args.suffix=args.results_folder+'/all_weights.npy'
    np.save(args.suffix,np.array(all_w))
    
    

#    Saving png plots
    coeff = torch.tensor(coeff)
    for i in range(coeff.shape[0]):
        a=torch.zeros(coeff[i].shape[0]).long()
        b=torch.arange(0, coeff[i].shape[0])
        c=torch.where(((coeff[i] > -0.1) & (coeff[i] < 0.1)),b,a)
        z = torch.zeros(coeff[i].shape[0]).fill_(0)
        z[torch.nonzero(c)] = coeff[i][torch.nonzero(c)]
        z = np.array(z)
        plt.plot(z)
    plt.xlabel('Dimension', fontsize=14)
    plt.ylabel('Coefficient', fontsize=14)
    pnpy = args.results_folder+'/plot1'
    plt.savefig(pnpy, format='png', pad_inches=5)


    return args.results_folder


def get_batch_samples(iter_no, args, mdl):
    """Return inputs and outputs belonging to batch given iteration number."""
    if args.batch_size == 0:
        return None, None

    num_batches = int(np.ceil(len(mdl.inputs) / args.batch_size))
    mod_iter_no = iter_no % num_batches
    start = mod_iter_no * args.batch_size
    end = (mod_iter_no + 1) * args.batch_size
    inputs = mdl.inputs[start:end]
    targets = mdl.targets[start:end]
    return inputs, targets








if __name__ == '__main__':
    args.results_folder = main()
    print("\n\n The code has been successfully executed!!\n\n")
    #a11 = yes_or_no_image()
    #if a11 == True :
    #    pnpy = str(args.results_folder) + '/plot1' + '.png'
    #    import cv2 
    #    img = cv2.imread(pnpy)  
    #    cv2.imshow('Plot', img)  
    #    cv2.waitKey(0)         
    #    cv2.destroyAllWindows() 
    #    print("\n\n Tata!!\n\n")
    #else:
    #    print("\n\n Tata!!\n\n")
    # 
    print("\n===============================================================================================\n")
