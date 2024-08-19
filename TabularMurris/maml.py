import torch
import torch.nn as nn
from collections import OrderedDict
from learner import FCNet
import numpy as np
from torch.distributions import Beta
import random

class MAML(nn.Module):
    def __init__(self, args):
        super(MAML, self).__init__()
        self.args = args
        self.learner = FCNet(args=args, x_dim=2866, hid_dim=64)
        self.loss_fn = nn.CrossEntropyLoss()
        if self.args.train:
            self.num_updates = self.args.num_updates
        else:
            self.num_updates = self.args.num_updates_test
        self.dist = Beta(torch.FloatTensor([2]), torch.FloatTensor([2]))

    def forward(self, xs, ys, xq, yq):
        create_graph = True

        fast_weights = OrderedDict(self.learner.named_parameters())

        for inner_batch in range(self.num_updates):
            logits = self.learner.functional_forward(xs, fast_weights, is_training=True)
            loss = self.loss_fn(logits, ys)
            gradients = torch.autograd.grad(loss, fast_weights.values(), create_graph=create_graph)

            fast_weights = OrderedDict(
                (name, param - self.args.update_lr * grad)
                for ((name, param), grad) in zip(fast_weights.items(), gradients)
            )

        query_logits = self.learner.functional_forward(xq, fast_weights)
        query_loss = self.loss_fn(query_logits, yq)

        y_pred = query_logits.softmax(dim=1).max(dim=1)[1]
        query_acc = (y_pred == yq).sum().float() / yq.shape[0]

        return query_loss, query_acc


    def forward_MLQA(self, x1s, y1s, x1q, y1q, x2s, y2s, x2q, y2q):

        sel_layer = 1

        shuffle_list = np.arange(self.args.num_classes)
        np.random.shuffle(shuffle_list)

        shuffle_list = np.append(shuffle_list, shuffle_list[0])

        shuffle_dict = {shuffle_list[i + 1]: shuffle_list[i] for i in range(self.args.num_classes)}

        shuffle_channel_id = np.random.choice(6)

        create_graph = True

        fast_weights = OrderedDict(self.learner.named_parameters())

        for inner_batch in range(self.args.num_updates):
            logits, s_label = self.learner.functional_forward_cf(x1s, y1s, sel_layer, shuffle_dict, shuffle_channel_id,
                                                                 fast_weights,
                                                                 is_training=True)

            loss = self.loss_fn(logits, s_label)

            gradients = torch.autograd.grad(loss, fast_weights.values(), create_graph=create_graph)

            fast_weights = OrderedDict(
                (name, param - self.args.update_lr * grad if 'net.1' in name or 'logits' in name else param)
                for ((name, param), grad) in zip(fast_weights.items(), gradients)
            )

        query_logits, q_label, s_label, lam = self.learner.functional_forward_MLQA(x1s, y1s, x2s, y2s, x1q, y1q, x2q, y2q,
                                                                                            sel_layer, 
                                                                                            shuffle_dict,
                                                                                            shuffle_channel_id,
                                                                                            fast_weights,
                                                                                            is_training=True)
        query_loss = self.loss_fn(query_logits, q_label)

        y_pred = query_logits.softmax(dim=1).max(dim=1)[1]
        query_acc = (y_pred == q_label).sum().float() / q_label.shape[0]

        return query_loss, query_acc


