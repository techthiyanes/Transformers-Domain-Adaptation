"""Class definition for Eurlex57k Dataset"""
from typing import Tuple
import unicodedata

import pandas as pd
import torch
from torch.utils.data import Dataset
import tokenizers
from sklearn.preprocessing import MultiLabelBinarizer

from src.tokenizer import truncate


class Eurlex57kDataset(Dataset):
    TEXT_COLS = ['header', 'recitals', 'attachments', 'main_body']

    def __init__(self,
                 eurlex57k: pd.DataFrame,
                 mode: str,
                 tokenizer: tokenizers.Tokenizer):
        eurlex57k = eurlex57k.copy()
        if mode not in ('train', 'dev', 'test'):
            raise ValueError('Incorrect value "{mode}" specified for `mode`')
        if mode not in eurlex57k['dataset'].values:
            raise ValueError(f'Mode "{mode}" does not exist in '
                             'Eurlex57k dataframe')
        if not hasattr(tokenizer, 'encode_batch'):
            raise ValueError('Tokenizer does not contain .encode_batch method')

        # Filter dataframe for appropriate data set
        df = eurlex57k[eurlex57k['dataset'] == mode]
        if not set(self.TEXT_COLS) <= set(df.columns):
            raise ValueError(f'Dataframe has to contain {self.TEXT_COLS} columns')
        if not len(df):
            raise ValueError(f'No values after filtering Eurlex57k for {mode}')

        # Perform minor ETL
        df['main_body_original'] = df['main_body']
        df['main_body'] = df['main_body'].apply(lambda x: '\n'.join(x))

        self.texts = self.preprocess_texts(df[self.TEXT_COLS])

        self.examples = (
            [truncate(enc.ids)
             for enc in tokenizer.encode_batch(self.texts.tolist())]
        )

        # Fit a multilabel encoder
        train_df = eurlex57k[eurlex57k['dataset'] == 'train']
        self.multi_label_encoder = MultiLabelBinarizer().fit(train_df['concepts'])
        self.labels = (
            torch.tensor(self.multi_label_encoder.transform(df['concepts']),
                         dtype=torch.long)
        )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, item: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return (torch.tensor(self.examples[item], dtype=torch.long),
                self.labels[item])

    @staticmethod
    def preprocess_texts(df):
        """Assumption: All columns in `df` are text columns."""
        return (
            df
            .apply(lambda row: ' '.join(word for text_col in row for word in text_col.split()), axis=1)
            .apply(lambda x: unicodedata
                             .normalize('NFKD', x)
                             .encode('ascii', 'ignore')
                             .decode("utf-8"))
        )
