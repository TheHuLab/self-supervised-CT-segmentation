# -*- coding: utf-8 -*-

"""Preview
Code for 'Inf-Net: Automatic COVID-19 Lung Infection Segmentation from CT Scans'
submit to Transactions on Medical Imaging, 2020.

First Version: Created on 2020-05-13 (@author: Ge-Peng Ji)
"""

import torch
from torch.utils.data.dataloader import DataLoader
from torch.autograd import Variable
import os
import argparse
from datetime import datetime
from Code.utils.dataloader_LungInf import get_loader
from Code.utils.utils import clip_gradient, adjust_lr, AvgMeter
import torch.nn.functional as F
from tensorboardX import SummaryWriter

from InfNet.Code.utils.dataloader_LungInf import test_dataset

global_current_iteration = 0


def joint_loss(pred, mask):
    weit = 1 + 5*torch.abs(F.avg_pool2d(mask, kernel_size=31, stride=1, padding=15) - mask)
    wbce = F.binary_cross_entropy_with_logits(pred, mask, reduce='none')
    wbce = (weit*wbce).sum(dim=(2, 3)) / weit.sum(dim=(2, 3))

    pred = torch.sigmoid(pred)
    inter = ((pred * mask)*weit).sum(dim=(2, 3))
    union = ((pred + mask)*weit).sum(dim=(2, 3))
    wiou = 1 - (inter + 1)/(union - inter+1)
    return (wbce + wiou).mean()


def train(train_loader, test_loader, model, optimizer, epoch, train_save, device):
    global global_current_iteration

    model.train()
    # ---- multi-scale training ----
    size_rates = [0.75, 1, 1.25]    # replace your desired scale, try larger scale for better accuracy in small object
    loss_record1, loss_record2, loss_record3, loss_record4, loss_record5 = AvgMeter(), AvgMeter(), AvgMeter(), AvgMeter(), AvgMeter()
    for i, pack in enumerate(train_loader, start=1):
        global_current_iteration += 1
        for rate in size_rates:
            optimizer.zero_grad()
            # ---- data prepare ----
            images, gts, edges = pack
            images = Variable(images).to(device)
            gts = Variable(gts).to(device)
            edges = Variable(edges).to(device)
            # ---- rescaling the inputs (img/gt/edge) ----
            trainsize = int(round(opt.trainsize*rate/32)*32)
            if rate != 1:
                images = F.upsample(images, size=(trainsize, trainsize), mode='bilinear', align_corners=True)
                gts = F.upsample(gts, size=(trainsize, trainsize), mode='bilinear', align_corners=True)
                edges = F.upsample(edges, size=(trainsize, trainsize), mode='bilinear', align_corners=True)

            # ---- forward ----
            lateral_map_5, lateral_map_4, lateral_map_3, lateral_map_2, lateral_edge = model(images)
            # ---- loss function ----
            loss5 = joint_loss(lateral_map_5, gts)
            loss4 = joint_loss(lateral_map_4, gts)
            loss3 = joint_loss(lateral_map_3, gts)
            loss2 = joint_loss(lateral_map_2, gts)
            loss1 = BCE(lateral_edge, edges)
            loss = loss1 + loss2 + loss3 + loss4 + loss5

            train_writer.add_scalar('edge_loss', loss1.item(), global_current_iteration)
            train_writer.add_scalar('loss2', loss2.item(), global_current_iteration)
            train_writer.add_scalar('loss3', loss3.item(), global_current_iteration)
            train_writer.add_scalar('loss4', loss4.item(), global_current_iteration)
            train_writer.add_scalar('loss5', loss5.item(), global_current_iteration)
            scalar_total_loss = loss2.item() + loss3.item() + loss4.item() + loss5.item()
            train_writer.add_scalar('total_loss', scalar_total_loss, global_current_iteration)

            # ---- backward ----
            loss.backward()
            clip_gradient(optimizer, opt.clip)
            optimizer.step()
            # ---- recording loss ----
            if rate == 1:
                loss_record1.update(loss1.data, opt.batchsize)
                loss_record2.update(loss2.data, opt.batchsize)
                loss_record3.update(loss3.data, opt.batchsize)
                loss_record4.update(loss4.data, opt.batchsize)
                loss_record5.update(loss5.data, opt.batchsize)
        # ---- train logging ----
        if i % 20 == 0 or i == total_step:
            print('{} Epoch [{:03d}/{:03d}], Step [{:04d}/{:04d}], [lateral-edge: {:.4f}, '
                  'lateral-2: {:.4f}, lateral-3: {:0.4f}, lateral-4: {:0.4f}, lateral-5: {:0.4f}]'.
                  format(datetime.now(), epoch, opt.epoch, i, total_step, loss_record1.show(),
                         loss_record2.show(), loss_record3.show(), loss_record4.show(), loss_record5.show()))
        # check testing error
        if global_current_iteration % 20 == 0:
            for pack in test_loader:
                image, gt, name = pack
                image = Variable(image).to(device)
                gt = Variable(gt).to(device)
                # ---- forward ----
                lateral_map_5, lateral_map_4, lateral_map_3, lateral_map_2, lateral_edge = model(image)
                # ---- loss function ----
                loss5 = joint_loss(lateral_map_5, gt)
                loss4 = joint_loss(lateral_map_4, gt)
                loss3 = joint_loss(lateral_map_3, gt)
                loss2 = joint_loss(lateral_map_2, gt)
                loss = loss2 + loss3 + loss4 + loss5

                test_writer.add_scalar('loss2', loss2.item(), global_current_iteration)
                test_writer.add_scalar('loss3', loss3.item(), global_current_iteration)
                test_writer.add_scalar('loss4', loss4.item(), global_current_iteration)
                test_writer.add_scalar('loss5', loss5.item(), global_current_iteration)
                scalar_testing_total_loss = loss2.item() + loss3.item() + loss4.item() + loss5.item()
                test_writer.add_scalar('total_loss', scalar_testing_total_loss, global_current_iteration)


    # ---- save model_lung_infection ----
    save_path = './Snapshots/save_weights/{}/'.format(train_save)
    os.makedirs(save_path, exist_ok=True)

    if (epoch+1) % 10 == 0:
        torch.save(model.state_dict(), save_path + 'Inf-Net-%d.pth' % (epoch+1))
        print('[Saving Snapshot:]', save_path + 'Inf-Net-%d.pth' % (epoch+1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # hyper-parameters
    parser.add_argument('--epoch', type=int, default=100,
                        help='epoch number')
    parser.add_argument('--lr', type=float, default=1e-4,
                        help='learning rate')
    parser.add_argument('--batchsize', type=int, default=24,
                        help='training batch size')
    parser.add_argument('--trainsize', type=int, default=352,
                        help='set the size of training sample')
    parser.add_argument('--clip', type=float, default=0.5,
                        help='gradient clipping margin')
    parser.add_argument('--decay_rate', type=float, default=0.1,
                        help='decay rate of learning rate')
    parser.add_argument('--decay_epoch', type=int, default=50,
                        help='every n epochs decay learning rate')
    parser.add_argument('--is_thop', type=bool, default=True,
                        help='whether calculate FLOPs/Params (Thop)')
    parser.add_argument('--gpu_device', type=int, default=0,
                        help='choose which GPU device you want to use')
    parser.add_argument('--num_workers', type=int, default=8,
                        help='number of workers in dataloader. In windows, set num_workers=0')
    parser.add_argument('--device', type=str, default='cpu')
    # model_lung_infection parameters
    parser.add_argument('--net_channel', type=int, default=32,
                        help='internal channel numbers in the Inf-Net, default=32, try larger for better accuracy')
    parser.add_argument('--n_classes', type=int, default=1,
                        help='binary segmentation when n_classes=1')
    parser.add_argument('--backbone', type=str, default='ResNet50',
                        help='change different backbone, choice: VGGNet16, ResNet50, Res2Net50')
    # training dataset
    parser.add_argument('--train_path', type=str,
                        default='./Dataset/TrainingSet/LungInfection-Train/Doctor-label')
    parser.add_argument('--is_semi', type=bool, default=False,
                        help='if True, you will turn on the mode of `Semi-Inf-Net`')
    parser.add_argument('--is_pseudo', type=bool, default=False,
                        help='if True, you will train the model on pseudo-label')
    parser.add_argument('--train_save', type=str, default=None,
                        help='If you use custom save path, please edit `--is_semi=True` and `--is_pseudo=True`')
    parser.add_argument('--is_data_augment', type=bool, default=False)

    # testing dataset
    parser.add_argument('--test_path', type=str, default="./Dataset/TestingSet/LungInfection-Test/")
    parser.add_argument('--testsize', type=int, default=352, help='testing size')

    # load model path
    parser.add_argument('--load_net_path', type=str)

    # save log tensorboard
    parser.add_argument('--graph_path', type=str, default="./graph_log")

    opt = parser.parse_args()

    # ---- build models ----
    # torch.cuda.set_device(opt.gpu_device)

    if opt.backbone == 'Res2Net50':
        print('Backbone loading: Res2Net50')
        from Code.model_lung_infection.InfNet_Res2Net import Inf_Net
    elif opt.backbone == 'ResNet50':
        print('Backbone loading: ResNet50')
        from Code.model_lung_infection.InfNet_ResNet import Inf_Net
    elif opt.backbone == 'VGGNet16':
        print('Backbone loading: VGGNet16')
        from Code.model_lung_infection.InfNet_VGGNet import Inf_Net
    else:
        raise ValueError('Invalid backbone parameters: {}'.format(opt.backbone))
    model = Inf_Net(channel=opt.net_channel, n_class=opt.n_classes).to(opt.device)

    if opt.load_net_path:
        net_state_dict = torch.load(opt.load_net_path)
        model.load_state_dict(net_state_dict)

    # ---- load pre-trained weights (mode=Semi-Inf-Net) ----
    # - See Sec.2.3 of `README.md` to learn how to generate your own img/pseudo-label from scratch.
    if opt.is_semi and opt.backbone == 'Res2Net50':
        print('Loading weights from weights file trained on pseudo label')
        model.load_state_dict(torch.load('./Snapshots/save_weights/Inf-Net_Pseduo/Inf-Net_pseudo_100.pth'))
    else:
        print('Not loading weights from weights file')

    # weights file save path
    if opt.is_pseudo and (not opt.is_semi):
        train_save = 'Inf-Net_Pseudo'
    elif (not opt.is_pseudo) and opt.is_semi:
        train_save = 'Semi-Inf-Net'
    elif (not opt.is_pseudo) and (not opt.is_semi):
        train_save = 'Inf-Net'
    else:
        print('Use custom save path')
        train_save = opt.train_save
    train_save = opt.train_save

    # ---- calculate FLOPs and Params ----
    if opt.is_thop:
        from Code.utils.utils import CalParams
        x = torch.randn(1, 3, opt.trainsize, opt.trainsize).to(opt.device)
        CalParams(model, x)

    # ---- load training sub-modules ----
    BCE = torch.nn.BCEWithLogitsLoss()

    train_writer = SummaryWriter(logdir=os.path.join(opt.graph_path, 'training'))
    test_writer = SummaryWriter(logdir=os.path.join(opt.graph_path, 'testing'))

    params = model.parameters()
    optimizer = torch.optim.Adam(params, opt.lr)

    image_root = '{}/Imgs/'.format(opt.train_path)
    gt_root = '{}/GT/'.format(opt.train_path)
    edge_root = '{}/Edge/'.format(opt.train_path)

    train_loader = get_loader(image_root, gt_root, edge_root,
                              batchsize=opt.batchsize, trainsize=opt.trainsize, num_workers=opt.num_workers,
                              is_data_augment=opt.is_data_augment)

    test_image_root = '{}/Imgs/'.format(opt.test_path)
    test_gt_root = '{}/GT/'.format(opt.test_path)
    test_data = test_dataset(test_image_root, test_gt_root, opt.testsize)
    test_loader = DataLoader(test_data, batch_size=opt.batchsize, num_workers=opt.num_workers)

    total_step = len(train_loader)

    # ---- start !! -----
    print("#"*20, "\nStart Training (Inf-Net-{})\n{}\nThis code is written for 'Inf-Net: Automatic COVID-19 Lung "
                  "Infection Segmentation from CT Scans', 2020, arXiv.\n"
                  "----\nPlease cite the paper if you use this code and dataset. "
                  "And any questions feel free to contact me "
                  "via E-mail (gepengai.ji@163.com)\n----\n".format(opt.backbone, opt), "#"*20)

    for epoch in range(1, opt.epoch):
        adjust_lr(optimizer, opt.lr, epoch, opt.decay_rate, opt.decay_epoch)
        train(train_loader,test_loader, model, optimizer, epoch, train_save, opt.device)
