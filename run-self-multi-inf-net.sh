# check again maybe batchsize can be changed
python main_multi-inf-net.py --save_path model/self_multi_improved --graph_path graph_self_multi_improved --device cuda --seed 7

# baseline
python MyTrain_MulClsLungInf_UNet.py --save_path multi-inf-net --random_cutout 0  --graph_path graph_multi-inf-net --device cuda --epoch 500 --batchsize 8

# self-supervised
python MyTrain_MulClsLungInf_UNet.py --save_path self-multi-inf-net --random_cutout 0 --graph_path graph_self-multi-inf-net --load_net_path ../model/self_multi_improved/medseg_resnet18_autoencoder_no_bottleneck_use_coach10.net.best.ckpt.t7--device cuda --epoch 500 --batchsize 8
python MyTrain_MulClsLungInf_UNet.py --save_path self-multi-improved-inf-net --is_data_augment True --random_cutout 0.5 --is_label_smooth True --graph_path graph_self-multi-inf-net --load_net_path ../model/self_multi_improved/medseg_resnet18_autoencoder_no_bottleneck_use_coach10.net.best.ckpt.t7--device cuda --epoch 500 --batchsize 8

