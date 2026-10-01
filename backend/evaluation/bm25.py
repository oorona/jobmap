"""Transparent BM25 baseline (k1=1.2, b=.75), no embeddings or inference."""
import math
import re
from collections import Counter


def words(text):
    return re.findall(r'[a-z0-9]+',text.lower())


class BM25:
    def __init__(self,jobs):
        self.jobs=jobs
        self.counts=[Counter(words(j['search_text'])) for j in jobs]
        self.lengths=[sum(c.values()) for c in self.counts]
        self.average=sum(self.lengths)/max(1,len(jobs))
        self.df=Counter(term for counts in self.counts for term in counts)

    def search(self,query,limit=30):
        output=[]
        for job,counts,length in zip(self.jobs,self.counts,self.lengths):
            score=0
            for term in set(words(query)):
                tf=counts[term]
                if tf:
                    idf=math.log(1+(len(self.jobs)-self.df[term]+.5)/(self.df[term]+.5))
                    score+=idf*tf*2.2/(tf+1.2*(.25+.75*length/self.average))
            output.append({'id':job['id'],'relevance':score})
        return sorted(output,key=lambda r:(-r['relevance'],r['id']))[:limit]
