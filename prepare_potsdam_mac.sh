#!/bin/bash

# set paths
potsdam_root=/Users/darylfung/programming/Self-supervision-for-segmenting-overhead-imagery/datasets
potsdam_splits=$potsdam_root/splits/
potsdam_img_root=$potsdam_root/RELEASE_FOLDER/2_Ortho_RGB/
potsdam_gt_root=$potsdam_root/RELEASE_FOLDER/5_Labels_for_participants/
potsdam_stride=200

echo 'creating directories for images and gt crops for train and validation splits'
mkdir -p $potsdam_root/processed/train/images/ $potsdam_root/processed/train/gt/ $potsdam_root/processed/val/images/ $potsdam_root/processed/val/gt/

echo 'creating train crops with stride of' ${potsdam_stride} x ${potsdam_stride}
while read -r line; do 
	echo 'processing ' $line;
	python utils/color_map_to_class_index.py ${potsdam_gt_root}/${line}_label.tif ${potsdam_gt_root}/${line}_label.png potsdam
	for ((row=0;row<=600;row+=200)); do
		pids="";
		for ((col=0;col<=600;col+=200)); do
			echo 'creating ' ${line}_${row}_${col};
			convert ${potsdam_img_root}/${line}_RGB.tif -crop 600x600+${col}+${row} ${potsdam_root}/processed/train/images/${line}_${row}_${col}.jpg 2>/dev/null &
			convert ${potsdam_gt_root}/${line}_label.png -crop 600x600+${col}+${row} ${potsdam_root}/processed/train/gt/${line}_${row}_${col}.png 2>/dev/null &
			pids="$pids $!";
		done;
		wait $pids;
	done;
done < ${potsdam_splits}/train.txt

potsdam_stride=600
echo 'creating val crops with stride of' ${potsdam_stride} x ${potsdam_stride}
while read -r line; do 
	echo 'processing ' $line;
	python utils/color_map_to_class_index.py ${potsdam_gt_root}/${line}_label.tif ${potsdam_gt_root}/${line}_label.png potsdam
	for ((row=0;row<=600;row+=600)); do
		pids="";
		for ((col=0;col<=600;col+=200)); do
			echo 'creating ' ${line}_${row}_${col};
			convert ${potsdam_img_root}/${line}_RGB.tif -crop 600x600+${col}+${row} ${potsdam_root}/processed/val/images/${line}_${row}_${col}.jpg 2>/dev/null &
			convert ${potsdam_gt_root}/${line}_label.png -crop 600x600+${col}+${row} ${potsdam_root}/processed/val/gt/${line}_${row}_${col}.png 2>/dev/null &
			pids="$pids $!";
		done;
		wait $pids;
	done;
done < ${potsdam_splits}/val.txt

