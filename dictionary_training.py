
import numpy as np
import pyroomacoustics as pra
import matplotlib.pyplot as plt
import os
import pickle

from sklearn.decomposition import NMF

from multinmf_conv_em import multinmf_conv_em_dictionary_training


def nmf_train(training_set, n_latent_variables, solver='mu', n_iter=200, gamma=None, W=None, H=None):
    '''
    NMF using the Itakura-Saito divergence and l1 regularization for sparse activations.

    Parameters
    ----------
    examples: list of array_like (n_examples, n_bins, n_frames)
        Tensor containing all the spectrograms to decompose
    n_latent_variables: int
        Number of latent variables in the NMF
    n_iter: int
        Number of iterations
    gamma: float
        Regularization paramters
    W: array_like, optional
        Initialization for W
    H: array_like, optional
        Initialization for activations
    '''

    model = NMF(n_components=n_latent_variables, solver='mu', beta_loss=0,\
        max_iter=n_iter, init='custom')

    dictionary = []

    i = 1
    n_items = len(training_set)
    for speaker, spectrograms in training_set.items():
        print('speaker %d/%d'%(i,n_items))
        # initialization
        n_bins, n_frames = spectrograms.shape
        pwr_psd = np.mean(spectrograms, axis=1)  # average spectral power
        W = (0.1 + np.abs(np.random.randn(n_bins, n_latent_variables))) * np.sqrt(pwr_psd[:,None])
        pwr_act = np.mean(spectrograms, axis=0)  # average activation power
        H = (0.1 + np.abs(np.random.randn(n_latent_variables, n_frames))) * np.sqrt(pwr_act[None,:])

        # train
        dictionary.append(model.fit_transform(spectrograms, W=W, H=H))

        i += 1
    return np.concatenate(dictionary, axis=1)


if __name__ == '__main__':

    stft_win_len = 2048
    n_speakers = 1  # number of speakers per gender
    n_latent_variables = 20
    n_iter = 300  # number of iterations of NMF per speaker
    solver = "em"

    # add an environment variable with the TIMIT location
    # e.g. /path/to/timit/TIMIT
    try:
        # timit_path = os.environ['TIMIT_PATH']
        timit_path = '/home/ddicarlo/Documents/Datasets/TIMIT/TIMIT'
    except:
        raise ValueError('An environment variable ''TIMIT_PATH'' pointing to the TIMIT base location is needed.')

    # Load the corpus, be patient
    cache_file = '.timit_corpus_cache.pickle'
    if os.path.exists(cache_file):
        print('Load cached TIMIT corpus...')
        with open(cache_file, 'rb') as f:
            corpus = pickle.load(f)
    else:
        print('Load TIMIT corpus...')
        corpus = pra.TimitCorpus(timit_path)
        corpus.build_corpus()
        print('Cache TIMIT corpus...')
        with open(cache_file, 'wb') as f:
            pickle.dump(corpus, f)

    # let's find all the sentences from male speakers in the training set
    male_speakers_test = list(set([s.speaker for s in filter(lambda x: x.sex == 'M', corpus.sentence_corpus['TEST'])]))
    male_speakers_train = list(set([s.speaker for s in filter(lambda x: x.sex == 'M', corpus.sentence_corpus['TRAIN'])]))
    female_speakers_test = list(set([s.speaker for s in filter(lambda x: x.sex == 'F', corpus.sentence_corpus['TEST'])]))
    female_speakers_train = list(set([s.speaker for s in filter(lambda x: x.sex == 'F', corpus.sentence_corpus['TRAIN'])]))

    print('Pick a subset of', n_speakers, 'speakers')
    training_set_speakers = male_speakers_train[:n_speakers] + female_speakers_train[:n_speakers]
    print(training_set_speakers)

    # compute all the spectrograms
    print('Compute all the spectrograms')
    window = np.sqrt(pra.cosine(stft_win_len))  # use sqrt because of synthesis
    training_set = dict()
    testing_set = dict()
    for speaker in training_set_speakers:
        training_set_sentences = filter(lambda x: x.speaker == speaker, corpus.sentence_corpus['TRAIN'])
        # X is (n_sentences, n_channel, n_frame)
        x = list()
        X = list()
        for sentence in training_set_sentences:
            print(sentence.speaker, sentence.id,)
            x.append(sentence.samples)
            X.append(pra.stft(sentence.samples, stft_win_len, stft_win_len // 2, win=window, transform=np.fft.rfft).T)
        # TRAIN:
        # Dalia says the magnitude works better...
        training_set[speaker] = np.concatenate([np.abs(spectrogram)**2 for spectrogram in X[0:9]], axis=1)
        # TEST:
        testing_set[speaker] = x[-1]

    print('Train the dictionary...')
    W_dictionary = nmf_train(training_set, n_latent_variables, n_iter=n_iter)
    W_dictionary /= np.sum(W_dictionary, axis=0)[None,:]
    np.savez('W_dictionary_em.npz', speakers=list(training_set.keys()), W_dictionary=W_dictionary, testing_set=testing_set)
