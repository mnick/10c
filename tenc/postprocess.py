import logging

log = logging.getLogger('tenc')


def tfidf(X):
    logging.debug('Running tf-idf postprocessing')
    from sklearn.feature_extraction.text import TfidfTransformer
    t = TfidfTransformer(use_idf=True, smooth_idf=True)
    return t.fit_transform(X)
