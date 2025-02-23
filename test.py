import tensorflow_hub as hub
import tensorflow as tf
from keras import Input, Model
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.engine import Layer
from keras.layers import Embedding, LSTM, Dense, Bidirectional, Lambda, TimeDistributed
import keras.backend as K
from tensorflow.python.keras.backend import concatenate

from evaluation.eval import get_wnut_evaluation
from utils.util import ReadFile
"""
def get_available_devices():
    local_device_protos = K.device_lib.list_local_devices()
    return [x.name for x in local_device_protos]

get_available_devices()
"""

elmo_model = 'https://tfhub.dev/google/elmo/2'


# tf.compat.v1.disable_eager_execution()
class ElmoEmbeddingLayer(Layer):
    def __init__(self, **kwargs):
        self.dimensions = 1024
        self.trainable = True
        super(ElmoEmbeddingLayer, self).__init__(**kwargs)

    def build(self, input_shape):
        self.elmo = hub.Module('https://tfhub.dev/google/elmo/2', trainable=self.trainable,
                               name="{}_module".format(self.name))

        self.trainable_weights += tf.trainable_variables(scope="^{}_module/.*".format(self.name))
        super(ElmoEmbeddingLayer, self).build(input_shape)

    def call(self, x, mask=None):
        result = self.elmo(inputs={
            "tokens": tf.squeeze(tf.cast(x, tf.string)),
            "sequence_len": tf.constant(50 * [100])
        },
            signature="tokens",
            as_dict=True)["elmo"]
        return result


def DeepContextualRepresentation(x):
    sess = tf.Session()
    K.set_session(sess)
    elmo_model = hub.Module("https://tfhub.dev/google/elmo/2", trainable=True)
    sess.run(tf.global_variables_initializer())
    sess.run(tf.tables_initializer())
    return elmo_model(inputs={
        "tokens": tf.squeeze(tf.cast(x, "string")),
        "sequence_len": tf.constant(50 * [100])
    },
        signature="tokens",
        as_dict=True)["elmo"]
def ner_classifier():
    file = ReadFile()
    obj = ReadFile()
    X, x_tr, x_val, x_ts, y_tr, y_val, y_ts = file.wrapper_sequences()
    x_tr = obj.sequence_helper(x_tr, 100)
    x_val = obj.sequence_helper(x_val, 100)
    x_ts = obj.sequence_helper(x_ts, 100)
    print(len(x_ts))
    print(len(x_val))
    print(len(x_tr))
    print(len(y_ts))
    print(len(y_val))
    print(len(x_tr))
    word_input = Input(shape=(100,), dtype="string")
    embedding = Lambda(DeepContextualRepresentation, output_shape=(100, 1024))(word_input)
    bi_rnn = Bidirectional(LSTM(units=256,
                               return_sequences=True,
                               activation='tanh',
                               dropout=0.3,
                               recurrent_dropout=0.3)) (embedding)

    prediction_layer = (Dense(units=21, activation='softmax'))(bi_rnn)
    model = Model(inputs=word_input, outputs=prediction_layer)
    import numpy as np
    y_tr = np.asarray(y_tr)
    y_val = np.asarray(y_val)
    y_ts = np.asarray(y_ts)
    print(y_tr.shape)
    y_tr = y_tr.reshape(y_tr.shape[0], y_tr.shape[1],1)
    y_val = y_val.reshape(y_val.shape[0], y_val.shape[1],1)
    y_ts = y_ts.reshape(y_ts.shape[0], y_ts.shape[1],1)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.summary()
    #callback = EarlyStopping(monitor= 'val_loss', patience=2 )
    checkpointer = ModelCheckpoint(filepath= 'model.hdf5',
                                   verbose=1,
                                   save_best_only=True)
    earlystopper = EarlyStopping(monitor='val_loss',
                                 patience=1,
                                 verbose=1)
    

    model.fit(np.array(x_tr), np.array(y_tr),
        validation_data=[np.asarray(x_val), np.asarray(y_val)],
        batch_size=50,
        epochs=1,
        callbacks=[checkpointer, earlystopper])
    prediction = model.predict(np.asarray(x_ts), batch_size=50, verbose=1)

    prediction = np.argmax(prediction, axis=-1)
    print('printing the classification results')
    #print(sklearn.metrics.classification.classification_report(np.array(y_ts), np.array(prediction)))
    obj = ReadFile()
    true = obj.getLabels(y_ts, vocabulary=obj.get_label_vocab())
    pred = obj.getLabels(prediction, vocabulary=obj.get_label_vocab())
    obj.save_predictions('result.tsv', x_ts, true, pred )
    get_wnut_evaluation('result.tsv')

if __name__ == '__main__':
    ner_classifier()
