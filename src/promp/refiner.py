from bbolib.bbo.cost_function import CostFunction
from bbolib.bbo.distribution_gaussian import DistributionGaussian
from bbolib.bbo.updater import UpdaterCovarDecay
from bbolib.bbo.run_optimization import runOptimization
from .ik import FK
import numpy as np


class RefiningCostFunction(CostFunction):
    """ CostFunction in which the distance to the goal and the task-space (or joint-space) jerk must be minimized."""
    def __init__(self, arm, goal, num_basis, Gn, alpha, beta):
        self.goal = goal
        self.alpha = alpha
        self.beta = beta
        self.Gn = Gn
        self.fk = FK(arm)
        self.num_joints = len(self.fk.joints)
        self.num_basis = num_basis

    def weights_to_trajectories(self, sample):
        trajectory = []
        for joint in range(self.num_joints):
            trajectory.append(np.dot(self.Gn, sample[joint*self.num_basis:(joint + 1) * self.num_basis]))
        return np.array(trajectory).T

    def cost_precision(self, trajectory):
        return np.linalg.norm(np.array(self.goal[0]) - np.array(self.fk.get(trajectory[-1])[0]))

    def cost_joint_jerk(self, trajectory):
        trajectory_t = trajectory.T
        jerk = [np.absolute(np.diff(np.diff(np.diff(joint)))) for joint in trajectory_t]
        return np.sum(jerk)

    def cost_cartesian_jerk(self, trajectory):
        cartesian_traj = np.array([self.fk.get(point)[0] for point in trajectory]).T
        jerk = [np.absolute(np.diff(np.diff(np.diff(point)))) for point in cartesian_traj]
        return np.sum(jerk)

    def evaluate(self, sample):
        # Compute distance from sample to point
        trajectory = self.weights_to_trajectories(sample)
        cost_jerk = self.cost_cartesian_jerk(trajectory)
        cost_precision = self.cost_precision(trajectory)
        cost = self.alpha * cost_jerk + self.beta * cost_precision, cost_jerk, cost_precision
        return cost


class TrajectoryRefiner(object):
    def __init__(self, arm, num_basis, Gn, factor_jerk=1, factor_precision=1, n_samples_per_update=20, n_updates=100):
        self.arm = arm
        self.num_basis = num_basis
        self.Gn = Gn
        self.factor_jerk = factor_jerk
        self.factor_precision = factor_precision
        self.n_samples_per_update = n_samples_per_update
        self.n_updates = n_updates

    def refine_trajectory(self, mean, cov, goal):
        """
        Refine a trajectory to reach goal more precisely from the given input trajectory
        :param mean: Mean of weights of the input trajectory
        :param cov: Covariance of the input trajectory
        :param goal: [[x, y, z], [x, y, z, w]]
        :return: the refined mean of weights
        """
        distribution = DistributionGaussian(mean, cov)

        eliteness = 10
        weighting_method = 'PI-BB'
        covar_decay_factor = 0.8
        updater = UpdaterCovarDecay(eliteness, weighting_method, covar_decay_factor)
        cost_function = RefiningCostFunction(self.arm, goal, self.num_basis, self.Gn, self.factor_jerk, self.factor_precision)

        #import matplotlib.pyplot as plt
        #fig = plt.figure(1, figsize=(15, 5))

        mean, cov = runOptimization(cost_function, distribution, updater, self.n_updates, self.n_samples_per_update)  #, fig, '/tmp/freek')
        return mean