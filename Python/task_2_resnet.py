# -*- coding: utf-8 -*-
"""Task_2_Resnet.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1w7PLmW5eZGDzC5F0PtTf3tURtWgl8xIt

# Task 2: ResNet-18

### Import Dependencies and download "Tiny-ImageNet-200" dataset.
"""

# Mounting Google drive for loading the checkpoint.

from google.colab import drive
drive.mount('/content/gdrive')

!cd gdrive/MyDrive/

!wget http://cs231n.stanford.edu/tiny-imagenet-200.zip
!unzip -q tiny-imagenet-200.zip && ls tiny-imagenet-200

import os
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import Dataset
from torchvision import datasets
from torchvision import transforms
from torchvision.transforms import ToTensor, Lambda
import torchvision.models as models
from torch.hub import load_state_dict_from_url


torch.cuda.empty_cache()
cuda = torch.device('cuda') 
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print('Using {} device'.format(device))

"""### Preprocessing: Collate all image's path address & labels as a input to custom pytorch dataset"""

file_list = []


for folder in os.listdir('./tiny-imagenet-200/train/'):


  label = folder 
  for file in os.listdir('./tiny-imagenet-200/train/' + folder + '/images/'):
    file_dir = './tiny-imagenet-200/train/' + folder + '/images/' + file

    file_list.append((file_dir))

with open('./tiny-imagenet-200/wnids.txt',) as f:

  id_list = {}
  read_data = f.readlines()
  for i, val in enumerate(read_data):
    id_list[val.replace('\n', '')] = i


test_list = []
test_id = {}
with open('./tiny-imagenet-200/val/val_annotations.txt', 'r') as f:
  for line in f.readlines():
    file, label = line.split()[0:2]
    file_dir = './tiny-imagenet-200/val/images/' + file

    test_list.append((file_dir))
    test_id[file] = label

"""### Custom Pytorch datatset for training images of "Tiny-ImageNet-200" dataset."""

class TrainTinyImageNetDataset(Dataset):
    def __init__(self, f_list, id, transform=None):

        self.filenames = f_list
        self.transform = transform
        self.id_dict = id

    def __len__(self):
        return len(self.filenames)

    def __getitem__(self, idx):

        img_path = self.filenames[idx]
        image = None
       
        with open(img_path, 'rb') as f:
          image = Image.open(f)
          image =  image.convert('RGB')
          
        
       

        label = self.id_dict[img_path.split('/')[-1].split('.')[0].split('_')[0]]
       

        if self.transform is not None:

            image = self.transform(image)
            
        return image, label


class TrainSet(TrainTinyImageNetDataset):
  
    def __init__(self, f_list, id, transform=None):

        super(TrainSet, self).__init__(f_list, id, transform=transform)

"""### Custom Pytorch datatset for testing images of "Tiny-ImageNet-200" dataset."""

class TestTinyImageNetDataset(Dataset):
    def __init__(self, t_list, id, cls_id, transform=None):
        self.filenames = t_list
        self.transform = transform
        self.id_dict = id
        self.cls_id = cls_id
       


    def __len__(self):
        return len(self.filenames)

    def __getitem__(self, idx):
        img_path = self.filenames[idx]
        image = None
       
        with open(img_path, 'rb') as f:
          image = Image.open(f)
          image =  image.convert('RGB')
    
        label = self.cls_id[self.id_dict[img_path.split('/')[-1]]]
        
        if self.transform is not None:
            image = self.transform(image)
        return image, label

"""### CUBS Block 1"""

class CUBS1(nn.Module):
  def __init__(self, channels_in, n_in):
      super(CUBS1, self).__init__()
      self.channels_in = channels_in
      self.n_in = n_in
      self.dense_1_1 = nn.Linear(channels_in,n_in)
      self.dense_1_2 = nn.Linear(channels_in,n_in)
      self.dense_1_3 = nn.Linear(channels_in,n_in)
      self.dense_2 = nn.Linear(n_in,channels_in)
      self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

    

      self.relu = nn.ReLU(inplace=True)
      self.sig = nn.Sigmoid()


  def CB1_Sim1(self, a, b):
    a_norm = torch.nn.functional.normalize(a, dim=2)
    b_norm = torch.nn.functional.normalize(b, dim=2)

    sim_matrix = torch.matmul(a_norm[0].T, b_norm[0])
    sim_matrix = sim_matrix.reshape((1,self.n_in,self.n_in))


    for i in range(1,a.shape[0]):
  
      mul = torch.matmul(a_norm[i].T, b_norm[i]) 
      mul = mul.reshape((1,self.n_in,self.n_in))
      sim_matrix = torch.vstack((sim_matrix,mul))
      

    

    return sim_matrix


  def CB1_Sim2(self, a, b):
    b_norm = torch.nn.functional.normalize(b, dim=2)

    sim_matrix = torch.matmul(a[0], b_norm[0].T)
    sim_matrix = sim_matrix.reshape((1,1,self.n_in))


    for i in range(1,a.shape[0]):
      mul = torch.matmul(a[i], b_norm[i].T)
      mul = mul.reshape((1,1,self.n_in))
      sim_matrix = torch.vstack((sim_matrix,mul))

    return sim_matrix

  def CB1_Softmax(self, a):
    out_matrix = nn.Softmax(dim=1)(a[0])
    out_matrix = out_matrix.reshape((1,self.n_in,self.n_in))

    for i in range(1,a.shape[0]):
      sim = nn.Softmax(dim=1)(a[i])
      sim = sim.reshape((1,self.n_in,self.n_in))
      out_matrix = torch.vstack((out_matrix,sim))

    return out_matrix

  def CB1_Channel(self, a, b):
    out_matrix = b[0] * a[0].unsqueeze(dim=-1). unsqueeze(dim=-1)

    for i in range(1,a.shape[0]): 
      mul = b[i] * a[i].unsqueeze(dim=-1). unsqueeze(dim=-1)
      out_matrix = torch.vstack((out_matrix,mul))

    return out_matrix

      
  

  def forward(self, x):
      x_pool = self.avgpool(x)
      x_pool = torch.reshape(x_pool,(x.shape[0],1,x.shape[1]))

     

      x_1_1 = self.dense_1_1(x_pool)
     
      
      x_1_1 = self.relu(x_1_1)

      x_1_2 = self.dense_1_2(x_pool)
      x_1_2 = self.relu(x_1_2)

      x_1_3 = self.dense_1_3(x_pool)
      x_1_3 = self.relu(x_1_3)

     
      x_1_2_sim = self.CB1_Sim1(x_1_1, x_1_2)


            
      x_1_2_softmax = self.CB1_Softmax(x_1_2_sim)

  
      x_1_2_3_sim = self.CB1_Sim2(x_1_3, x_1_2_softmax)
      
      x_2 = self.dense_2(x_1_2_3_sim)
      x_2 = self.relu(x_2)

      x_concat_1 = torch.add(x_2, x_pool)
      x_sig = self.sig(x_concat_1)


      x_out = self.CB1_Channel(x_sig, x)
      return x_out

"""### CUBS Block 2"""

class CUBS2(nn.Module):
  def __init__(self, channels_in, n_in):
      super(CUBS2, self).__init__()
      self.channels_in = channels_in
      self.n_in = n_in


      self.conv_1_1 = nn.Conv2d(channels_in, 1, kernel_size=1)
      self.conv_1_2 = nn.Conv2d(channels_in, 1, kernel_size=1)
      self.conv_1_3 = nn.Conv2d(channels_in, 1, kernel_size=1)
      
   
      
      self.relu = nn.ReLU(inplace=True)

      self.sig = nn.Sigmoid()


  def CB2_Sim1(self, a, b):

      a = torch.flatten(a, start_dim=2, end_dim=3)    
      b = torch.flatten(b, start_dim=2, end_dim=3)

      a_norm = torch.nn.functional.normalize(a, dim=2)
      b_norm = torch.nn.functional.normalize(b, dim=2)

      sim_matrix = torch.matmul(a_norm[0].T, b_norm[0])
      sim_matrix = sim_matrix.reshape((1,a.shape[2],a.shape[2]))


      for i in range(1,a.shape[0]):
    
        mul = torch.matmul(a_norm[i].T, b_norm[i]) 
        mul = mul.reshape((1,a.shape[2],a.shape[2]))
        sim_matrix = torch.vstack((sim_matrix,mul))
        

      return sim_matrix


  def CB2_Sim2(self, a, b):

      a = torch.flatten(a, start_dim=2, end_dim=3)
      b_norm = torch.nn.functional.normalize(b, dim=2)

      sim_matrix = torch.matmul(a[0], b_norm[0].T)
      sim_matrix = sim_matrix.reshape((1,1,a.shape[2]))


      for i in range(1,a.shape[0]):
        mul = torch.matmul(a[i], b_norm[i].T)
        mul = mul.reshape((1,1,a.shape[2]))
        sim_matrix = torch.vstack((sim_matrix,mul))

      return sim_matrix


  def CB2_Softmax(self, a):
      out_matrix = nn.Softmax(dim=1)(a[0])
      out_matrix = out_matrix.reshape((1,a.shape[2],a.shape[2]))

      for i in range(1,a.shape[0]):
        sim = nn.Softmax(dim=1)(a[i])
        sim = sim.reshape((1,a.shape[2],a.shape[2]))
        out_matrix = torch.vstack((out_matrix,sim))

      return out_matrix

  

  def bmul(self, vec, mat, axis=0):
      mat = mat.transpose(axis, -1)
      return (mat * vec.expand_as(mat)).transpose(axis, -1)

  def CB1_Pixel(self, a, b):
      a = torch.reshape(a, (a.shape[0],b.shape[2],b.shape[3]))
    
      a_0 = a[0]
      b_0 = b[0]
      out_matrix = self.bmul(a_0,b_0, axis=2)
      out_matrix = out_matrix.reshape((1,b.shape[1],b.shape[2],b.shape[3]))

      for i in range(1, a.shape[0]):
        ai = a[i]
        
        bi = b[i]
      
        mul = self.bmul(ai,bi, axis=2)
        mul = mul.reshape((1,b.shape[1],b.shape[2],b.shape[3]))
        out_matrix = torch.vstack((out_matrix,mul))

      return out_matrix
      
  def forward(self, x):

     
      x_1_1 = self.conv_1_1(x)
      x_1_1 = self.relu(x_1_1)

      x_1_2 = self.conv_1_2(x)
      x_1_2 = self.relu(x_1_2)

      x_1_3 = self.conv_1_3(x)
      x_1_3 = self.relu(x_1_3)

     
      x_1_2_sim = self.CB2_Sim1(x_1_1, x_1_2)

      x_1_2_softmax = self.CB2_Softmax(x_1_2_sim)

     
      x_1_2_3_sim = self.CB2_Sim2(x_1_3, x_1_2_softmax)
      
      x_sig = self.sig(x_1_2_3_sim)

     
      x_out = self.CB1_Pixel(x_sig, x)
      
      return x_out

"""### This section contains Open-Sourced "ResNet-18" implementation along with various modifications and CUBS Blocks(1 & 2) experiments mentioned in the assignment.

***

### I've modified the "BasicBlock" of open-sourced ResNet-18 implementations to get new "BasicBlock_A", "BasicBlock_B" and "BasicBlock_C" defining the all 3 different configurations that were given as a task.

***

### BasicBlock_A : Parallel CUBS 1 & CUBS 2
### BasicBlock_B : CUBS 1 -> CUBS 2
### BasicBlock_C : CUBS 2 -> CUBS 1


"""

__all__ = ['ResNet', 'resnet18', 'resnet34', 'resnet50', 'resnet101',
           'resnet152', 'resnext50_32x4d', 'resnext101_32x8d',
           'wide_resnet50_2', 'wide_resnet101_2']


model_urls = {
    'resnet18': 'https://download.pytorch.org/models/resnet18-5c106cde.pth',
    'resnet34': 'https://download.pytorch.org/models/resnet34-333f7ec4.pth',
    'resnet50': 'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    'resnet101': 'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
    'resnet152': 'https://download.pytorch.org/models/resnet152-b121ed2d.pth',
    'resnext50_32x4d': 'https://download.pytorch.org/models/resnext50_32x4d-7cdf4587.pth',
    'resnext101_32x8d': 'https://download.pytorch.org/models/resnext101_32x8d-8ba56ff5.pth',
    'wide_resnet50_2': 'https://download.pytorch.org/models/wide_resnet50_2-95faca4d.pth',
    'wide_resnet101_2': 'https://download.pytorch.org/models/wide_resnet101_2-32ee1156.pth',
}


def conv3x3(in_planes, out_planes, stride=1, groups=1, dilation=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=dilation, groups=groups, bias=False, dilation=dilation)


def conv1x1(in_planes, out_planes, stride=1):
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(BasicBlock, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out



class BasicBlock_A(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(BasicBlock_A, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride
        self.cubs1 = CUBS1(planes, 30)
        self.cubs2 = CUBS2(planes, 30)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        # Parallel CUBS 1 & CUBS 2
        out_cubs1 = self.cubs1(out)
        out_cubs2 = self.cubs2(out)

        out = out_cubs1 + out_cubs2

        out += identity
        out = self.relu(out)

        return out


class BasicBlock_B(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(BasicBlock_B, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride
        self.cubs1 = CUBS1(planes, 30)
        self.cubs2 = CUBS2(planes, 30)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        # CUBS 1 -> CUBS 2
        out = self.cubs1(out)
        out = self.cubs2(out)

        out += identity
        out = self.relu(out)

        return out


class BasicBlock_C(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(BasicBlock_C, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride
        self.cubs1 = CUBS1(planes, 30)
        self.cubs2 = CUBS2(planes, 30)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        # CUBS 2 -> CUBS 1
        out = self.cubs2(out)
        out = self.cubs1(out)

        out += identity
        out = self.relu(out)

        return out



class Bottleneck(nn.Module):
    # Bottleneck in torchvision places the stride for downsampling at 3x3 convolution(self.conv2)
    # while original implementation places the stride at the first 1x1 convolution(self.conv1)
    # according to "Deep residual learning for image recognition"https://arxiv.org/abs/1512.03385.
    # This variant is also known as ResNet V1.5 and improves accuracy according to
    # https://ngc.nvidia.com/catalog/model-scripts/nvidia:resnet_50_v1_5_for_pytorch.

    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None, groups=1,
                 base_width=64, dilation=1, norm_layer=None):
        super(Bottleneck, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        width = int(planes * (base_width / 64.)) * groups
        # Both self.conv2 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv1x1(inplanes, width)
        self.bn1 = norm_layer(width)
        self.conv2 = conv3x3(width, width, stride, groups, dilation)
        self.bn2 = norm_layer(width)
        self.conv3 = conv1x1(width, planes * self.expansion)
        self.bn3 = norm_layer(planes * self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(self, block, layers, num_classes=200, zero_init_residual=False,
                 groups=1, width_per_group=64, replace_stride_with_dilation=None,
                 norm_layer=None):
        super(ResNet, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        self._norm_layer = norm_layer

        self.inplanes = 64
        self.dilation = 1
        if replace_stride_with_dilation is None:
            # each element in the tuple indicates if we should replace
            # the 2x2 stride with a dilated convolution instead
            replace_stride_with_dilation = [False, False, False]
        if len(replace_stride_with_dilation) != 3:
            raise ValueError("replace_stride_with_dilation should be None "
                             "or a 3-element tuple, got {}".format(replace_stride_with_dilation))
        self.groups = groups
        self.base_width = width_per_group
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = norm_layer(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2,
                                       dilate=replace_stride_with_dilation[0])
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2,
                                       dilate=replace_stride_with_dilation[1])
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2,
                                       dilate=replace_stride_with_dilation[2])
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512 * block.expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        # Zero-initialize the last BN in each residual branch,
        # so that the residual branch starts with zeros, and each residual block behaves like an identity.
        # This improves the model by 0.2~0.3% according to https://arxiv.org/abs/1706.02677
        if zero_init_residual:
            for m in self.modules():
                if isinstance(m, Bottleneck):
                    nn.init.constant_(m.bn3.weight, 0)
                elif isinstance(m, BasicBlock):
                    nn.init.constant_(m.bn2.weight, 0)

    def _make_layer(self, block, planes, blocks, stride=1, dilate=False):
        norm_layer = self._norm_layer
        downsample = None
        previous_dilation = self.dilation
        if dilate:
            self.dilation *= stride
            stride = 1
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes * block.expansion, stride),
                norm_layer(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, self.groups,
                            self.base_width, previous_dilation, norm_layer))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, groups=self.groups,
                                base_width=self.base_width, dilation=self.dilation,
                                norm_layer=norm_layer))

        return nn.Sequential(*layers)

    def _forward_impl(self, x):
        # See note [TorchScript super()]
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)

        return x

    def forward(self, x):
        return self._forward_impl(x)


def _resnet(arch, block, layers, pretrained, progress, **kwargs):
    model = ResNet(block, layers, **kwargs)
    if pretrained:
        state_dict = load_state_dict_from_url(model_urls[arch],
                                              progress=progress)
        model.load_state_dict(state_dict)
    return model

"""### Defining 4 different models for vanilla ResNet-18, Model_A, Model_B & Model_C with different variations of "BasicBlock"."""

def resnet18(pretrained=False, progress=True, **kwargs):
    r"""ResNet-18 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet18', BasicBlock, [2, 2, 2, 2], pretrained, progress,
                   **kwargs)
    

def model_A(pretrained=False, progress=True, **kwargs):
    r"""ResNet-18 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet18', BasicBlock_A, [2, 2, 2, 2], pretrained, progress,
                   **kwargs)
    

def model_B(pretrained=False, progress=True, **kwargs):
    r"""ResNet-18 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet18', BasicBlock_B, [2, 2, 2, 2], pretrained, progress,
                   **kwargs)
    

def model_C(pretrained=False, progress=True, **kwargs):
    r"""ResNet-18 model from
    `"Deep Residual Learning for Image Recognition" <https://arxiv.org/pdf/1512.03385.pdf>`_

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    return _resnet('resnet18', BasicBlock_C, [2, 2, 2, 2], pretrained, progress,
                   **kwargs)

"""### Training Function"""

def train(dataloader, model, loss_fn, optimizer):
    size = len(dataloader.dataset)
    model.train()
    for batch, (X, y) in enumerate(dataloader):
      
        X, y = X.to(device), y.long().to(device)
        optimizer.zero_grad()
        torch.set_grad_enabled(True)
        
        pred = model(X).float()
       
        loss = loss_fn(pred, y)

       
        loss.backward()
        optimizer.step()

    
        if batch % 1000 == 0:
            loss, current = loss.item(), batch * len(X)
            print(f"loss: {loss:>7f}  [{current:>5d}/{size:>5d}]")

"""### Testing Function"""

def test(dataloader, model, loss_fn):
    size = len(dataloader.dataset)
    num_batches = len(dataloader)
    model.eval()
    test_loss, correct = 0, 0
    with torch.no_grad():
        for X, y in dataloader:
          
            X, y = X.to(device), y.long().to(device)
            torch.set_grad_enabled(False)
            pred = model(X).float()
       
            test_loss += loss_fn(pred, y).item()
            correct += (pred.argmax(1) == y).type(torch.float).sum().item()
    test_loss /= num_batches
    correct /= size
    print(f"Test Error: \n Accuracy: {(100*correct):>0.1f}%, Avg loss: {test_loss:>8f} \n")
    return test_loss

"""### Defining "Learning Rate Scheduler" & "Early stopping mechanism""""

class LRScheduler():
  
    def __init__(
        self, optimizer, patience=5, min_lr=1e-7, factor=0.75
    ):
        
        self.optimizer = optimizer
        self.patience = patience
        self.min_lr = min_lr
        self.factor = factor
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau( 
                self.optimizer,
                mode='min',
                patience=self.patience,
                factor=self.factor,
                min_lr=self.min_lr,
                verbose=True
            )
    def __call__(self, val_loss):
        self.scheduler.step(val_loss)


class EarlyStopping():
   
    def __init__(self, patience=10, min_delta=0):
      
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False
    def __call__(self, val_loss):
        if self.best_loss == None:
            self.best_loss = val_loss
        elif self.best_loss - val_loss > self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        elif self.best_loss - val_loss < self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

"""### Instantiating Dataset loaders for training & testing"""

normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225])

trans = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize,
        ])

trainset = TrainSet(f_list=file_list,id=id_list, transform=trans)
trainloader = torch.utils.data.DataLoader(trainset, batch_size=5, shuffle=True, num_workers=4)

trans_test = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            normalize,
        ])

testset = TestTinyImageNetDataset(t_list=test_list,id=test_id, cls_id =id_list,  transform=trans_test)
testloader = torch.utils.data.DataLoader(testset, batch_size=5, shuffle=False, num_workers=4)

"""### Instantiating & training & checkpoint vanilla "ResNet-18"

#### There are 2 cells for ResNet that are given below.
#### Run the 1st cell in case you want to load a checkpoint & resume training.
#### Else Run the 2nd cell in case you want to start training from scratch.

#### **NOTE: Make sure to change the path of loading the checkpoint in 1st cell**
"""

resnet18 = resnet18(pretrained=False, progress=True)
resnet18 = resnet18.to(device)
loss_fn = torch.nn.CrossEntropyLoss()
optimizer_resnet18 = torch.optim.Adam(resnet18.parameters(), lr=0.0001)


# **NOTE: Make sure to change the path of loading the checkpoint in 1st cell**
checkpoint = torch.load('gdrive/MyDrive/trained-resnet-model.ckpt')


resnet18.load_state_dict(checkpoint['model_state_dict'])
optimizer_resnet18.load_state_dict(checkpoint['optimizer_state_dict'])
epoch = checkpoint['epoch'] + 1
loss = checkpoint['loss']


es =  EarlyStopping()
lrs = LRScheduler(optimizer_resnet18)

checkpoint_dir = "."
test_loss = 0
epochs = 20
for i in range(epochs):
    print(f"Epoch {i+1}")
    train(trainloader, resnet18, loss_fn, optimizer_resnet18)
    test_loss = test(testloader, resnet18, loss_fn)

    torch.save({
        'epoch': i+1,
        'model_state_dict': resnet18.state_dict(),
        'optimizer_state_dict': optimizer_resnet18.state_dict(),
        'loss': test_loss
        }, checkpoint_dir+'/%04d-resnet18-model.ckpt' %i)
    
    lrs(test_loss)
    es(test_loss)
    if es.early_stop:
      break

"""#### Run the 2nd cell in case you want to start training from scratch."""

resnet18 = resnet18(pretrained=False, progress=True)
resnet18 = resnet18.to(device)
loss_fn = torch.nn.CrossEntropyLoss()
optimizer_resnet18 = torch.optim.Adam(resnet18.parameters(), lr=0.0001)

es =  EarlyStopping()
lrs = LRScheduler(optimizer_resnet18)

checkpoint_dir = "."
test_loss = 0
epochs = 20
for i in range(epochs):
    print(f"Epoch {i+1}")
    train(trainloader, resnet18, loss_fn, optimizer_resnet18)
    test_loss = test(testloader, resnet18, loss_fn)

    torch.save({
        'epoch': i+1,
        'model_state_dict': resnet18.state_dict(),
        'optimizer_state_dict': optimizer_resnet18.state_dict(),
        'loss': test_loss
        }, checkpoint_dir+'/%04d-resnet18-model.ckpt' %i)
    
    lrs(test_loss)
    es(test_loss)
    if es.early_stop:
      break



torch.save({
        'epoch': epochs,
        'model_state_dict': resnet18.state_dict(),
        'optimizer_state_dict': optimizer_resnet18.state_dict(),
        'loss': test_loss
        }, checkpoint_dir+'/final-resnet18-model.ckpt')