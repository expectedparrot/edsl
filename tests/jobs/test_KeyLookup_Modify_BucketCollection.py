import pytest
from edsl import Model 
from edsl import QuestionFreeText
from edsl.key_management import KeyLookup

def test_default_rpm_bucket_collection():
    # Create model with default RPM
    m = Model('test')
    jobs = QuestionFreeText.example().by(m)
    bc = jobs.create_bucket_collection()
    rr = bc[Model(model_name='test', temperature=0.5)].requests_bucket.refill_rate
    
    # Check if actual refill rate is within 10 requests/min of target RPM
    actual_rpm = rr * 60
    assert abs(actual_rpm - m.rpm) < 10, \
        f"Actual RPM ({actual_rpm}) differs from target RPM ({m.rpm}) by more than 10"

def test_custom_rpm_bucket_collection():
    # Setup custom RPM via KeyLookup
    kl = KeyLookup.example()
    target_rpm = 1
    kl['test'].rpm = target_rpm
    
    # Create jobs with custom KeyLookup
    m = Model('test')
    jobs = QuestionFreeText.example().by(m)
    jobs2 = jobs.using(kl)
    
    # Create bucket collection and get refill rate
    bc = jobs2.create_bucket_collection()
    rr = bc[Model(model_name='test', temperature=0.5)].requests_bucket.refill_rate
    
    # Check if actual refill rate is within 1 request/min of target RPM
    actual_rpm = rr * 60
    assert abs(actual_rpm - target_rpm) < 1, \
        f"Actual RPM ({actual_rpm}) differs from target RPM ({target_rpm}) by more than 1"


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
