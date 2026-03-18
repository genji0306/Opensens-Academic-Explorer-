[ -z "${expname}" ] && expname="test"

[ -z "${model}" ] && model="cpcp"
[ -z "${data_name}" ] && data_name="hmof_400"

[ -z "${freeze}" ] && freeze=false
[ -z "${max_seq_len}" ] && max_seq_len=2048
[ -z "${precision}" ] && precision=32
[ -z "${bsz}" ] && bsz=4
[ -z "${pretrained}" ] && pretrained=''
[ -z "${lr}" ] && lr=1e-4
[ -z "${betas}" ] && betas='[0.9, 0.999]'
[ -z "${eps}" ] && eps=1e-8
[ -z "${weight_decay}" ] && weight_decay=0.0

python xtalnet/run.py data=$data_name \
    expname=$expname \
    model=$model \
    model.freeze_pxrd_encoder=$freeze \
    model.pxrd_encoder.max_seq_len=$max_seq_len \
    train.pl_trainer.precision=$precision \
    data.datamodule.batch_size.train=$bsz \
    data.pretrained=$pretrained \
    optim.optimizer.lr=$lr \
    optim.optimizer.betas=$betas \
    optim.optimizer.eps=$eps \
    optim.optimizer.weight_decay=$weight_decay \

