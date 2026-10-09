// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'receipts.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Map<String, dynamic> _$DescribeRequestToJson(DescribeRequest instance) =>
    <String, dynamic>{'text': instance.text};

ScanResponse _$ScanResponseFromJson(Map<String, dynamic> json) => ScanResponse(
  items: (json['items'] as List<dynamic>)
      .map((e) => ParsedIngredient.fromJson(e as Map<String, dynamic>))
      .toList(),
);
