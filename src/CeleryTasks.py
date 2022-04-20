import glob
import logging
from ToolChainClassifier.ToolChainClassifier import ToolChainClassifier
from ToolChainSCDG.clogging.CustomFormatter import CustomFormatter
try:
    from .HE.HE_SEALS import F, RSA
except:
    from HE.HE_SEALS import F, RSA
import os
import dill
import celery
import json

# Celery config
# Client: 130.104.229.26
# Client: 130.104.229.85
IP = "130.104.229.84/qa1"  # Master node
HOST = f'rabbitmq:9a55f70a841f18b97c3a7db939b7adc9e34a0f1d@{IP}'

# HOST = 'localhost'

BROKER = f'amqp://{HOST}'
BACKEND= f'rpc://{HOST}'

app = celery.Celery('ToolChainFL', 
                    broker=BROKER, 
                    backend=BACKEND)

context, key = F.init_encrypt()
sk, pk       = RSA.generate_key()

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())

logc = logging.getLogger("CeleryTasksClassifier")
logc.setLevel(logging.INFO)
logc.addHandler(ch)
logc.propagate = False

log = logging.getLogger("CeleryTasksSCDG")
log.setLevel(logging.INFO)
log.addHandler(ch)
log.propagate = False

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = ROOT_DIR.replace("tasks","")

########################################
# SCDGs creation
########################################

@app.task
def start_scdg(** args):
    # Need to be imported here for correctness
    from ToolChainSCDG.ToolChainSCDG import ToolChainSCDG
    toolcl = ToolChainSCDG(print_sm_step=True,
                            print_syscall=True,
                            debug_error=True,
                            debug_string=True,
                            print_on=True,
                            is_from_tc=True)
    folderName  = args["folderName"]
    args_scdg = args["args_scdg"]
    families = args["families"]
    expl_method = args["expl_method"]
    last_familiy = "unknown"
    log.info(args)
    if os.path.isdir(folderName):
        subfolder = [os.path.join(folderName, f) for f in os.listdir(folderName) if os.path.isdir(os.path.join(folderName, f))]
        log.info(subfolder)
        for folder in subfolder:
            log.info("You are currently building SCDG for " + folder)
            args_scdg["exp_dir"] = args_scdg["exp_dir"].replace(last_familiy,folder.split("/")[-1])
            last_familiy = folder.split("/")[-1]
            files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            for file  in files:
                toolcl.build_scdg(args_scdg, file, expl_method,last_familiy,is_fl=True)
            families += last_familiy
    else:
        log.info("Error: you should insert a folder containing malware classified in their family folders\n(Example: databases/malware-inputs/Sample_paper")
        exit(-1)
    return 0

########################################
# Classifier
########################################

def save_object(obj, path):
    with open(path, 'wb+') as output:
        dill.dump(obj, output)

def load_object(path):
    with open(path, 'rb') as inp:
        return dill.load(inp)

def signature_to_json(path_sig):
    #Iterate through samples of cleanware to classify
    data = {}
    for signature in glob.glob(path_sig+'*_sig.gs'):
        f0 = open(signature,'r')
        signature = signature.split("/")[-1] # keep name as index
        data[signature] = {}
        row = 0
        for line in f0 :
            data[signature][row] = line
            row += 1
    logc.info(data)
    return data

@app.task
def initHE(v):
    import tenseal as ts
    v_enc = ts.ckks_vector(context,v)
    pem = RSA.serialize_pk(pk)
    return {"ctx":F.enc_to_string(context),"v":F.enc_to_string(v_enc), "pk": F.bytes_to_string(pem)}

@app.task
def decryption(**args):
    import tenseal as ts
    run_name  = args["run_name"]
    para = args["para"]
    classifier = args["classifier"]
    ctx = args["ctx"]
    nround = args["nround"]
    num = float(args["num"])
    pwd = ROOT_DIR
    trainer = load_object(os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    trainer.share_model = F.update_encrypt(key,context,para, num, trainer.share_model)
    save_object(trainer, os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    para = trainer.get_model_parameter()       
    ctx = F.string_to_bytes(args["ctx"])
    v_enc =  F.string_to_enc(args["v_enc"],context)
    v = v_enc.decrypt(key)
    v_enc = ts.ckks_vector(ts.context_from(ctx),v)
    return {"v":F.enc_to_string(v_enc), "para": para}

@app.task
def train(** args):
    ctx = F.string_to_bytes(args["ctx"])
    run_name  = args["run_name"]
    nround = args["nround"]
    input_path = args["input_path"]
    classifier = args["classifier"]
    args_class = args["args_class"]
    demonstration = args["demonstration"]
    client_id = args["client_id"]
    pwd = ROOT_DIR
    logc.info(run_name)

    if demonstration:
        input_path = input_path + "_client"+str(client_id)
        
    if nround<1:
        toolcl = ToolChainClassifier(classifier_name=classifier, parse=False)
        families = []
        last_familiy = "unknown"
        if os.path.isdir(input_path):
            subfolder = [os.path.join(input_path, f) for f in os.listdir(input_path) if os.path.isdir(os.path.join(input_path, f))]
            for folder in subfolder:
                last_familiy = folder.split("/")[-1]
                families.append(str(last_familiy))
        toolcl.init_classifer(args=args_class,families=families,is_fl=True)
        trainer = toolcl.classifier
        trainer.n_epochs = 1
    else:
        trainer = load_object(os.path.join(pwd,f"R{nround-1}_{run_name}_{classifier}_model.pkl"))
        trainer.n_epochs = 1
    
    if classifier == "dl":
        model, his = trainer.train(input_path)
    elif classifier == "gspan":
        trainer.train(input_path)
    else:
        exit(-1)
        
    save_object(trainer, os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    
    if classifier == "dl":
        para = F.encrypt_weight(ctx,trainer.share_model)
        return {"para":para,"his":his}
    elif classifier == "gspan": 
        # TODO graph concatenation instead
        data = signature_to_json(trainer.path_sig)
        data_string = json.dumps(data)
        master_pk = args["master_pk"]
        para = RSA.encrypt(master_pk,data_string)
        return {"para":para, "client_pk": F.bytes_to_string(RSA.serialize_pk(pk))}

@app.task
def update(**args):
    run_name  = args["run_name"]
    para = args["para"]
    v_enc = F.string_to_enc(args["v_enc"],context)
    classifier = args["classifier"]
    nround = args["nround"]
    pwd = ROOT_DIR
    trainer = load_object(os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    trainer.modelparameters = para
    save_object(trainer, f"{run_name}_model.pkl")
    save_object(trainer, os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    return {"v":v_enc.decrypt(key)}

@app.task
def best_signature_selection(**args):
    # best_fscore_familly = {}
    best_fscore = 0
    best_para = 0
    # Master node get all signature, 
    # test all signature and pick the best signature set (per familly TODO)
    clear_sig = ""
    idx = 0
    paras = args["paras"]
    args["client_pks"]
    for enc_sig in paras:
        for chunck in enc_sig:
            clear_sig += RSA.decrypt(sk,chunck)
        data_sig = json.loads(clear_sig)
        try:
            if os.path.isdir(ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/"):
                os.rmdir(ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/")
            os.mkdir(ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/")
        except:
            print('error')
            pass

        print(data_sig)

        for signature in data_sig:
            f = open(ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/" +  str(idx) + "/" + signature, "w")
            for line in data_sig[signature]:
                f.write(line)
            f.close()

        args["sigpath"] = ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/" +  str(idx) + "/" 
        ret_test = test(**args)
        fscore = float(ret_test[0]["fscore"])
        if fscore > best_fscore:
            best_fscore = fscore
            best_para = idx
    try:
        os.rename(ROOT_DIR+"/ToolChainClassifier/classifier/master_sig/"+ str(best_para) + "/" ,
            ROOT_DIR+"/ToolChainClassifier/classifier/best_sig/")
    except:
        print('error')
        pass

    best_sig_json = signature_to_json(ROOT_DIR+"/ToolChainClassifier/classifier/best_sig/")
    best_sig_string = json.dumps(best_sig_json)
    enc_best_sig_string = RSA.encrypt(pk,best_sig_string)
    return {"enc_best_sig_string": enc_best_sig_string}
                    

@app.task
def save_sig(**args):
    enc_best_sig_string = args["enc_best_sig_string"]
    idx = args["idx"]
    clear_sig = RSA.decrypt(sk,enc_best_sig_string[idx])
    data_sig = json.loads(clear_sig)
    try: # TODO for now we replace standard signature folder with best one
        if os.path.isdir(ROOT_DIR+"/ToolChainClassifier/classifier/sig/"):
            os.rmdir(ROOT_DIR+"/ToolChainClassifier/classifier/sig/")
        os.mkdir(ROOT_DIR+"/ToolChainClassifier/classifier/sig/")
    except:
        print('error')
        return {"v": -1}
    for signature in data_sig:
        f = open(ROOT_DIR+"/ToolChainClassifier/classifier/sig/"+signature, "w")
        for line in data_sig[signature]:
            f.write(line)
        f.close()
    return {"v": 0}
        
@app.task
def test(**args):
    nround = args["nround"]
    run_name  = args["run_name"]
    classifier = args["classifier"]
    pwd = ROOT_DIR
    trainer = load_object(os.path.join(pwd,f"R{nround}_{run_name}_{classifier}_model.pkl"))
    if classifier == "dl":
        trainer.classify() # TODO add custom path
        acc, loss = trainer.get_stat_classifier()
        return {"acc":acc, "loss":loss}
    elif classifier == "gpsan":
        sigpath = args["sigpath"]
        trainer.classify(custom_sig_path=sigpath) # TODO add custom path
        fscore = trainer.get_stat_classifier()
        return {"fscore":fscore}

