import threading
import os
import numpy as np
import tensorflow as tf
import keras

from actor_critic_model import A2CAgent
from network import FullyConv

from utils import *#Memory, record, generate_env

from pysc2 import maps
from pysc2.lib import actions
_NO_OP = actions.FUNCTIONS.no_op.id
_MOVE_SCREEN = actions.FUNCTIONS.Attack_screen.id
_SELECT_ARMY = actions.FUNCTIONS.select_army.id
_SELECT_POINT = actions.FUNCTIONS.select_point.id

class LossHistory(keras.callbacks.Callback):
    def on_train_begin(self, logs={}):
        self.losses = []

    def on_batch_end(self, batch, logs={}):
        self.losses.append(logs.get('loss'))

class Worker(threading.Thread):
    """This class implements a worker thread for the A3C algorithm.
    Args
    ----
    args (argparse.NameSpace): the namespace containing the command line arguments for the algorithm (initialized in main)"""

    # Set up global variables across different threads
    global_episode = 0
    # Moving average reward
    global_moving_average_reward = 0
    best_score = 0
    save_lock = threading.Lock()

    def __init__(self,
                 categorical_actions,
                 spatial_actions,
                 global_model,
                 opt,
                 result_queue,
                 idx,
                 game_name='MoveToBeacon',
                 save_dir='/save',
                 MAX_EPISODES =100,
                 MAX_STEPS = 400):
        super(Worker, self).__init__()
        #self.state_size = state_size
        #self.action_size = action_size
        self.result_queue = result_queue
        self.global_model = global_model
        self.opt = opt
        #self.local_model = ActorCriticModel(self.state_size, self.action_size)

        self.worker_idx = idx
        self.game_name = game_name
        self.env = generate_env(game_name)
        self.save_dir = save_dir
        self.ep_loss = 0.0

        self.MAX_EPISODES =100
        self.MAX_STEPS = 400

        self.spatial_actions = spatial_actions
        self.categorical_actions = categorical_actions
        self.id_from_actions = {}
        self.action_from_id = {}
        for ix,k in enumerate(spatial_actions):
            self.id_from_actions[k] = ix
            self.action_from_id[ix] = k
            for ix,k in enumerate(categorical_actions):
                self.id_from_actions[k]=ix+len(spatial_actions)
                self.action_from_id[ix+len(spatial_actions)] = k

        self.eta = 0.1
        self.expl_rate = 0.2

        #initialize model object
        model = FullyConv(self.eta, self.expl_rate, categorical_actions,spatial_actions)

        #initalize Agent
        self.agent = A2CAgent(model, categorical_actions,spatial_actions, self.id_from_actions,self.action_from_id)

    def discount_rewards(self, rewards):
        discounted_rewards = np.zeros_like(rewards)
        running_add = 0
        for t in reversed(range(0, len(rewards))):
            running_add = running_add * self.agent.gamma + rewards[t]
            discounted_rewards[t] = running_add
        return discounted_rewards
    def run(self):

        #FLAGS = flags.FLAGS
        #FLAGS(['run_sc2'])
        #MAX_EPISODES =100
        #MAX_STEPS = 400


        #steps = 0
        #FLAGS(['run_sc2'])
        #FLAGS(['run_sc2'])

        # create a map
        #beacon_map = maps.get('MoveToBeacon')


        #run trajectories and train
        try:
            # agent.load("./save/move_2_beacon-dqn.h5")

            done = False
            # batch_size = 5

            for e in range(self.MAX_EPISODES):
                #obs = env.reset()
                #score = 0
                #state = get_state(obs[0])
                #for time in range(self.MAX_STEPS):
                # env.render()
                    #init = False
                    #if e == 0 and time == 0:
                    #    init = True
                 #   a,point = self.agent.act(state, False)
                  #  if not a in obs[0].observation.available_actions:
                        a = _NO_OP
                   # func = get_action(a, point)
                    #next_obs = env.step([func])
                    #next_state = get_state(next_obs[0])
                    #reward = float(next_obs[0].reward)
                    #score += reward
                    #done = next_obs[0].last()
                    #agent.append_sample(state, a, reward,point)
                    #state = next_state
                    #obs = next_obs
                    #if done:
                    #    print("episode: {}/{}, score: {}"
                     #         .format(e, MAX_EPISODES, score))
                      #  break
                 #agent.train()
                #agent.save("./save/move_2_beacon-dqn.h5")



        #####
            total_step = 1
            mem = Memory()
            while Worker.global_episode < self.MAX_EPISODES:
                #current_state = self.env.reset()
                obs = self.env.reset()
                state = get_state(obs[0])

                mem.clear()
                ep_reward = 0.
                ep_steps = 0
                self.ep_loss = 0

                time_count = 0
                done = False
                while not done:
                    a,point = self.agent.act(state, False)
                    #To dO resample proba in available action space
                    if not a in obs[0].observation.available_actions:
                        a = _NO_OP
                    func = get_action(a, point)
                    next_obs = self.env.step([func])
                    next_state = get_state(next_obs[0])
                    reward = float(next_obs[0].reward)
                    #score += reward
                    done = next_obs[0].last()
                    #agent.append_sample(state, a, reward,point)

                    #if done:
                        #reward = -1
                    ep_reward += reward
                    mem.store(state, a, reward,point)
                    state = next_state
                    obs = next_obs

                    time_count += 1
                    total_step += 1
                    ep_steps += 1




                #if time_count == self.args.update_freq or done:
                # Calculate gradient wrt to local model. We do so by tracking the
                # variables involved in computing the loss by using tf.GradientTape
                with tf.GradientTape() as tape:
                    total_loss = self.compute_loss( mem,
                                                       self.agent.gamma)
                self.ep_loss += total_loss
                # Calculate local gradients
                grads = tape.gradient(total_loss, self.agent.model.trainable_weights)
                # Push local gradients to global model
                self.opt.apply_gradients(zip(grads,
                                             self.global_model.trainable_weights))
                # Update local model with new weights
                self.agent.model.set_weights(self.global_model.get_weights())

                #mem.clear()
                #time_count = 0

                 #if done:  # done and print information
                Worker.global_moving_average_reward = \
                    record(Worker.global_episode, ep_reward, self.worker_idx,
                           Worker.global_moving_average_reward, self.result_queue,
                           self.ep_loss, ep_steps)
                # We must use a lock to save our model and to print to prevent data races.
                if ep_reward > Worker.best_score:
                    with Worker.save_lock:
                        print("Saving best model to {}, "
                              "episode score: {}".format(self.save_dir, ep_reward))
                        self.global_model.save_weights(
                            os.path.join(self.save_dir,
                                         'model_{}.h5'.format(self.game_name))
                        )
                        Worker.best_score = ep_reward
                Worker.global_episode += 1
                self.agent.update_epsilon()
                self.result_queue.put(None)
        finally:
            self.env.close()
    def compute_loss(self,
                     #done,
                     #new_state,
                     memory,
                     gamma=0.99):

        history = LossHistory()
        episode_length = len(memory.states)
        discounted_rewards = self.discount_rewards(memory.rewards)
        # Standardized discounted rewards
        """discounted_rewards -= np.mean(discounted_rewards)
        if np.std(discounted_rewards):
            discounted_rewards /= np.std(discounted_rewards)
        else:
            self.states, self.actions, self.rewards = [], [], []
            #print ('std = 0!')
            return 0"""

        update_inputs = [np.zeros((episode_length, 17, 64, 64)),
                         np.zeros((episode_length, 7, 64, 64))]  # Episode_lengthx64x64x4

        # Episode length is like the minibatch size in DQN
        for i in range(episode_length):
            update_inputs[0][i, :, :, :] = memory.states[i][0][0, :, :, :]
            update_inputs[1][i, :, :, :] = memory.states[i][1][0, :, :, :]

        values = self.agent.model.predict(update_inputs)[0]

        advantages_actions = np.zeros((episode_length, len(self.id_from_actions)))
        advantages_space = np.zeros((episode_length, 4096))

        for i in range(episode_length):
            advantages_actions[i][self.id_from_actions[ memory.actions[i]]] = discounted_rewards[i] - values[i]
            advantages_space[i][self.id_from_actions[ memory.actions[i]]]= discounted_rewards[i] - values[i]
        with tf.Graph().as_default():
            self.agent.model.fit(update_inputs, [discounted_rewards, advantages_actions,advantages_space], nb_epoch=1, verbose=0,callbacks=[history])
        return history.losses[0]




        """if done:
            reward_sum = 0.  # terminal
#        else:
 #           reward_sum = self.agent.model(
              #  tf.convert_to_tensor(new_state[None, :],
              #                       dtype=tf.float32))[-1].numpy()[0]

        # Get discounted rewards
        discounted_rewards = []
        for reward in memory.rewards[::-1]:  # reverse buffer r
            reward_sum = reward + gamma * reward_sum
            discounted_rewards.append(reward_sum)
        discounted_rewards.reverse()

        s = [tf.convert_to_tensor(np.vstack(np.array([memory.states[k][0] for k in range(len(memory.states))]))),tf.convert_to_tensor(np.vstack(np.array([memory.states[k][1] for k in range(len (memory.states))])))]

        values,logits, spatial = self.agent.model(
            tf.convert_to_tensor(s))
        # Get our advantages
        advantage = tf.convert_to_tensor(np.array(discounted_rewards)[:, None],
                                         dtype=tf.float32) - values
        # Value loss
        value_loss = advantage ** 2

        # Calculate our policy loss
        policy = tf.nn.softmax(logits)
        entropy = tf.nn.softmax_cross_entropy_with_logits_v2(labels=policy, logits=logits)

        policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=memory.actions,
                                                                     logits=logits)
        policy_loss *= tf.stop_gradient(advantage)
        policy_loss -= 0.01 * entropy

         # Calculate our spatial loss
        policy_spatial = tf.nn.softmax(spatial)
        entropy = tf.nn.softmax_cross_entropy_with_logits_v2(labels=policy_spatial, logits=spatial)

        policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=memory.points,
                                                                     logits=spatial)
        policy_loss *= tf.stop_gradient(advantage)
        policy_loss -= 0.01 * entropy

        total_loss = tf.reduce_mean((0.5 * value_loss + policy_loss + spatial_loss))
        """

        #return total_loss
