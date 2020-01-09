import re
import pandas as pd
from collections import defaultdict, Counter
import numpy as np
import ahocorasick
import math


def read_text(file_articles, encoding='utf8'):
    texts = set()
    with open(file_articles, encoding=encoding) as f:
        for line in f.readlines():
            line = re.split(u'[^\u4e00-\u9fa50-9a-zA-Z]+', line)
            for s in line:
                if len(s) > 1:
                    texts.add(s)

    print('文章数(即文本行数)：{}'.format(len(texts)))
    return texts


def get_ngrams_counts(texts, n, min_count):
    '''
    返回ngrams出现的频数
    :param n: gram个数
    :param min_count: 最小出现次数，小于该值抛弃
    :return:
    '''
    ngrams = defaultdict(int)
    for t in list(texts):
        for i in range(len(t)):
            for j in range(1, n+1):
                if i+j <= len(t):
                    ngrams[t[i:i+j]] += 1

    ngrams = {i:j for i,j in ngrams.items() if j >= min_count}
    total = 1.*sum([j for i,j in ngrams.items() if len(i) == 1])
    print('字数：{}'.format(total))

    return ngrams, total




def filter_with_porba(s, min_proba, total, ngrams):
    '''
    统计凝固度，并根据阈值抛弃一定数量的词
    :param s:
    :param min_proba:
    :return:
    '''
    if len(s) >= 2:
        score = min([total*ngrams[s]/(ngrams[s[:i+1]]*ngrams[s[i+1:]]) for i in range(len(s)-1)])
        if score > min_proba[len(s)]:
            return True
    else:
        return False


def cut(s, n, ngrams):
    '''
    使用ngrams切分文本：采取宁愿不切，也不切错的原则
    :param s: 一段文本
    :param ngrams: 筛选过后的gram集合
    :return:
    '''
    # 统计文本每个长度大于2的子串在G中出现的次数
    r = np.array([0]*(len(s)-1))   # 大于2的片段频数统计
    for i in range(len(s)-1):
        for j in range(2, n+1):
            if s[i:i+j] in ngrams:
                r[i:i+j-1] += 1

    # 切分方法：只要有一个子串在G中，就不切分。只有当r中的统计次数为0时才切分一次。
    w = [s[0]]
    for i in range(1, len(s)):
        if r[i-1] > 0:
            w[-1] += s[i]
        else:
            w.append(s[i])
    return w


def is_real(s, n, ngrams):
    if len(s) >= 4:
        for i in range(4, n+1):
            for j in range(len(s)-i+1):
                if s[j:j+i] not in ngrams:
                    return False
        return True
    else:
        return True



def cal_entropy(dict_gram,key):
    '''
    计算gram的边界熵，分别计算左边界和右边界
    :param dict_gram:
    :param key:
    :return:
    '''
    left = dict_gram['left']
    if len(set(left)) ==1 and left[0] ==' ' :
        entropy_left = -1  # 如果左边界为空，则将其设置为-1
    else:
        list_left = list(Counter(left).values())
        sum_left = sum(list_left)
        entropy_left = sum([-(i / sum_left) * math.log(i / sum_left) for i in list_left])

    right = dict_gram['right']
    if  len(set(right)) ==1 and right[0] ==' ' :
        entropy_right = -1  # 如果右边界为空，则将其设置为-1
    else:
        list_right = list(Counter(right).values())
        sum_right = sum(list_right)
        entropy_right = sum([ -(i/sum_right)*math.log(i/sum_right) for i in list_right])

    if entropy_left==-1 and entropy_right==-1:
        entropy =-2   # 如果左右边界熵都为空，将其设置为-2
    else:
        entropy = min(entropy_left, entropy_right)
    return  entropy



class AC_Unicode:
    """稍微封装一下，弄个支持unicode的AC自动机
    """
    def __init__(self):
        self.ac = ahocorasick.Automaton()
    def add_word(self, k, v):
        # k = k.encode('utf-8')
        return self.ac.add_word(k, v)
    def make_automaton(self):
        return self.ac.make_automaton()
    def iter(self, s):
        # 搜索文本中存在的单词
        # s = s.encode('utf-8')
        return self.ac.iter(s)


def get_ngrams_neighbor_ac(texts, w):
    '''
       返回ngrams出现的左右相邻的字, 将所有文本拼接成一行，利用AC自动机一次匹配所有词
       根据匹配结果获取该词的左右字，从而计算边界熵
    '''
    neighbors = {}

    text_line  = ''
    for line in texts:
        text_line += ' '+ line

    print('构建AC自动机...')
    ac = AC_Unicode()
    for gram in w.keys():
        if len(gram)>1:
            ac.add_word(gram, gram)
    ac.make_automaton()
    result_ac = ac.iter(text_line)

    print('迭代匹配结果...')
    for item in result_ac:
        index, key = item
        if key not in neighbors.keys():
            neighbors[key] = {'left':[], 'right':[]}
        else:
            index_left = index-len(key) + 1
            if index_left-1 >= 0:
                neighbors[key]['left'].append(text_line[index_left-1 : index_left])

            index_right = index
            if index_left-1 <=  len(text_line):
                neighbors[key]['right'].append(text_line[index_right+1 : index_right+2])

    print('计算边界熵...')
    ngrams_entropy = defaultdict(int)
    for key in neighbors.keys():
        entropy = cal_entropy(neighbors[key], key)
        ngrams_entropy[key] = entropy
    return ngrams_entropy



def remove_general_words_ac(dict_general_words, ws):
    '''
    根据常用词词典移除常用词，将常用词典拼成长文本
    利用AC自动机匹配出现在长文本中词，并将其删除
    :param dict_general_words:
    :param ws:
    :return:
    '''
    print('移除常用词...')

    ac = AC_Unicode()
    for gram in ws.keys():
        if len(gram)>1:
            ac.add_word(gram, gram)

    General_dict = pd.read_csv(dict_general_words)
    General_dict = list(General_dict['0'].values)
    General_dict_ = ''
    for key in General_dict:
        General_dict_ += ' ' + str(key)

    ac.make_automaton()
    result_ac = ac.iter(General_dict_)
    for index, key in result_ac:
        try:
            del ws[key]
        except: continue
    final_w = sorted(ws.items(), key=lambda item: item[1],reverse=True)

    return final_w



def get_new_words( file_in, file_dict, file_out, min_count, min_proba):
    '''
    获取新词
    :param file_in: 按行存储的输入文档，每行可以看做一篇文章，utf8编码
    :param file_dict: 常用词词典，每行一个词
    :param file_out: 输出文件，每行一个词，和其对应的边界熵，按边界熵从打到小排列，gbk编码
    :param min_count: ngrams最小出现次数
    :param min_proba: 不同长度的词对应的最小凝固度阈值字典，这里输入长度为2,3,4的即可
    :return:
    '''
    import time
    start = time.time()

    n = 4 # 默认ngrams中的n为4
    texts = read_text(file_in, encoding='utf8')  # 读取数据
    ngrams, total = get_ngrams_counts(texts, n, min_count)  # 获取ngrams
    ngrams_filter = set(i for i, j in ngrams.items() if filter_with_porba(i, min_proba, total, ngrams))  # 计算凝固度，并根据阈值过滤ngrams

    # 根据ngrams分词
    words = defaultdict(int)
    for t in texts:
        for i in cut(t, n, ngrams_filter):
            words[i] += 1
    w = {i: j for i, j in words.items() if j >= min_count}  # 根据阈值筛选出出现频率较高的词

    # 注意此时的words和ngrams_filter,也就是凝固度集合，鄙视完全重合的。因为会分出来ngrams中没有的词。
    # w = {i: j for i, j in words.items() if is_real(i, n, ngrams_filter)}
    print('凝固度筛选词的长度：{}'.format(len(w)))

    ws = get_ngrams_neighbor_ac(texts, w)  # 按边界熵大小排序
    final_w = remove_general_words_ac(file_dict, ws)

    with open(file_out, 'w', encoding='gbk') as writer:
        for value in final_w:
            writer.write('{},{}\n'.format(value[0], value[1]))

    end = time.time()
    print('新词个数：{}'.format(len(final_w)))
    print('花费时间：{}分钟'.format(round((end - start) / 60, 2)))




if __name__ == '__main__':

    min_count = 2
    min_proba = {2: 50, 3: 1000, 4: 500}
    file_in = './weibo_text_mini.txt'   # utf8
    file_dict = './dict_sogou_vec.txt'  # utf8
    file_out = './find_words_.csv'  # gbk

    get_new_words(file_in, file_dict, file_out, min_count, min_proba)

