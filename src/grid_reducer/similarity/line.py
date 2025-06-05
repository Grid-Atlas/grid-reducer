from grid_reducer.similarity.similarity import CheckSimilarity


class LineSimilarity(CheckSimilarity):
    ignore_fields = {"Name", "Bus1", "Bus2", "Length", "Units"}
