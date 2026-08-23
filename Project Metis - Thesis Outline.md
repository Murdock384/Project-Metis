## Project Metis

## Metis: A Context-Aware Routine Planning System for Supporting Personal Well-Being

David Abraham - 487868
Mevin Biju - 4860974

## Aim

The aim of this thesis is to design a mobile app that supports personal well-being by helping users organize tasks, habits, activities, and transport-related time blocks within a realistic daily routine.

## Hypothesis

A context-aware routine planning system that combines adaptive task scheduling, habit tracking, and transport-aware planning can improve user productivity and reduce perceived stress.

## Planned Features

This section breaks down each of the major features we want to have along with their corresponding data sources and methods when applicable.

## Personalized User Preference

- Ask meaningful questions to users about their likes, dislikes, focus preferences, everyday routines.


- Reminders based on punctuality (subject to change)

## Dynamic Transport Services Integration

To implement the Dynamic transport services feature, we would like to utilize the following data sources and methods.

## Google Maps

## Feature

Show map

Calculate travel time

Convert address to coordinates

Search nearby gyms/cafes/activities

Autocomplete location input

## Jakdojade

- Leverage Jakdojade API (Reach out to kontakt@jakdojade.pl to request access) [URL 🔗](mailto:kontakt@jakdojade.pl)

Google API service that maybe needed

Maps JavaScript API

Routes API or Directions API

Geocoding API

Places API

Places API / Autocomplete

Documentation: https://docs.jakdojade.pl/restxml/connections/ [URL 🔗](https://docs.jakdojade.pl/restxml/connections/)

## Dynamic Tasks Integration

## Google Calendar

- User enters a flat list of items they want to do with each item having

- Difficulty

- Urgency

- Estimated time

- Category (Optional-Possibly Dynamic)

Each item will get converted to a timed event block on the calendar.


- Leveraging Google calendar to place user’s activities in suitable time blocks directly on the calendar. MVP is to have a widget view of the calendar in UI.

- Using Google OR Tools as a method to build a task scheduling engine [URL 🔗](https://developers.google.com/optimization)

## Dynamic Activities

## STEP 2

- Habit Tracking (Set frequency + Goals)

Is the activity something that requires going to a destination(Possible Transport Service support)

- Habit Commitment Analytics Dashboard (on a weekly/monthly basis)
