from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class EContentDescriptorID(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentDescriptor_NudityOrSexualContent: _ClassVar[EContentDescriptorID]
    k_EContentDescriptor_FrequentViolenceOrGore: _ClassVar[EContentDescriptorID]
    k_EContentDescriptor_AdultOnlySexualContent: _ClassVar[EContentDescriptorID]
    k_EContentDescriptor_GratuitousSexualContent: _ClassVar[EContentDescriptorID]
    k_EContentDescriptor_AnyMatureContent: _ClassVar[EContentDescriptorID]
    k_EContentDescriptorMAX: _ClassVar[EContentDescriptorID]

class EInteractiveElement(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EInteractiveElement_Invalid: _ClassVar[EInteractiveElement]
    k_EInteractiveElement_InGamePurchases: _ClassVar[EInteractiveElement]
    k_EInteractiveElement_InGamePurchasesOfRandomizedItems: _ClassVar[EInteractiveElement]
    k_EInteractiveElement_InGameChat: _ClassVar[EInteractiveElement]
    k_EInteractiveElement_OnlineInteractivity: _ClassVar[EInteractiveElement]
k_EContentDescriptor_NudityOrSexualContent: EContentDescriptorID
k_EContentDescriptor_FrequentViolenceOrGore: EContentDescriptorID
k_EContentDescriptor_AdultOnlySexualContent: EContentDescriptorID
k_EContentDescriptor_GratuitousSexualContent: EContentDescriptorID
k_EContentDescriptor_AnyMatureContent: EContentDescriptorID
k_EContentDescriptorMAX: EContentDescriptorID
k_EInteractiveElement_Invalid: EInteractiveElement
k_EInteractiveElement_InGamePurchases: EInteractiveElement
k_EInteractiveElement_InGamePurchasesOfRandomizedItems: EInteractiveElement
k_EInteractiveElement_InGameChat: EInteractiveElement
k_EInteractiveElement_OnlineInteractivity: EInteractiveElement
