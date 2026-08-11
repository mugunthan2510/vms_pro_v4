class AggregateRanker:
    def rank_universe(self, score_list):
        return sorted(score_list, key=lambda x: x['final_score'], reverse=True)
