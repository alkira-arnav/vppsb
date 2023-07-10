from yaml import safe_load, YAMLError
import logging


def load_yaml(file_path):
    if file_path is None:
        return None

    with open(file_path, "r") as file:
        try:
            return safe_load(file)

        except YAMLError as err:
            logging.error("Invalid yaml file: %s - %s", file_path, err)
            if hasattr(err, "problem_mark"):
                mark = err.problem_mark
                logging.error("Error at (%s:%s)", mark.line + 1, mark.column + 1)
            return None