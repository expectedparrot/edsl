import textwrap


def get_model_class(model_name):
    from edsl.inference_services.services_collection import collection
    factory = collection.create_model_factory(model_name)
    return factory      

class Meta(type):
    def __repr__(cls):
        return textwrap.dedent(
            f"""\
        Available models: {cls.available()}
        
        To create an instance, you can do: 
        >>> m = Model('gpt-4-1106-preview', temperature=0.5, ...)
        
        To get the default model, you can leave out the model name. 
        To see the available models, you can do:
        >>> Model.available()
        """
        )

class Model(metaclass=Meta):

    default_model = "gpt-4-1106-preview"

    def __new__(cls, model_name=None, *args, **kwargs):
        # Map index to the respective subclass
        if model_name is None:
            model_name = cls.default_model
        from edsl.inference_services.services_collection import collection
        factory = collection.create_model_factory(model_name)
        return factory(*args, **kwargs)
    
    @classmethod
    def from_index(cls, index, *args, **kwargs):
        from edsl.inference_services.services_collection import collection
        model_name = collection.available()[index][0]
        return cls(model_name, *args, **kwargs)

    @classmethod
    def available(cls, search_term = None, name_only = False):
        from edsl.inference_services.services_collection import collection
        full_list = collection.available()
        if search_term is None:
            if name_only:
                return [m[0] for m in full_list]
            else:
                return full_list
        else:
            filtered_results = [m for m in full_list if search_term in m[0] or search_term in m[1]]
            if name_only:
                return [m[0] for m in filtered_results]
            else:
                return filtered_results

    @classmethod
    def check_models(cls, verbose=False):
        print("Checking all available models...\n")
        for model in cls.available(name_only=True):
            print(f"Now checking: {model}")
            try:
                m = cls(model)
            except Exception as e:
                print(f"Error creating instance of {model}: {e}")
                continue
            try:
                results = m.hello(verbose)
                if verbose:
                    print(f"Results from model call: {results}")
            except Exception as e:
                print(f"Error calling 'hello' on {model}: {e}")
                continue
            print("OK!")
            print("\n")


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    available = Model.available()
    m = Model("gpt-4-1106-preview")
    results = m.execute_model_call("Hello world")
    print(results)
