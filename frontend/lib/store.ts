"use client";

import { useSyncExternalStore } from "react";

export type PanelView = "overview" | "load" | "call" | "invoice";

interface UIState {
  selectedLoadId: string | null;
  selectedDriverId: string | null;
  panelOpen: boolean;
  panelView: PanelView;
  fallbackMode: boolean;
}

const state: UIState = {
  selectedLoadId: null,
  selectedDriverId: null,
  panelOpen: false,
  panelView: "overview",
  fallbackMode: false,
};

const listeners = new Set<() => void>();
function emit() {
  for (const l of listeners) l();
}
function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

let snapshot: UIState = { ...state };
function commit() {
  snapshot = { ...state };
  emit();
}

export function selectLoad(loadId: string, driverId: string) {
  state.selectedLoadId = loadId;
  state.selectedDriverId = driverId;
  state.panelOpen = true;
  state.panelView = "load";
  commit();
}

export function selectDriver(driverId: string) {
  state.selectedDriverId = driverId;
  state.panelOpen = true;
  state.panelView = "load";
  commit();
}

export function closePanel() {
  state.panelOpen = false;
  commit();
}

export function openPanel(view: PanelView = "overview") {
  state.panelOpen = true;
  state.panelView = view;
  commit();
}

export function setPanelView(view: PanelView) {
  state.panelView = view;
  state.panelOpen = true;
  commit();
}

export function deselect() {
  state.selectedLoadId = null;
  state.selectedDriverId = null;
  state.panelView = "overview";
  commit();
}

export function setFallbackMode(on: boolean) {
  state.fallbackMode = on;
  commit();
}

export function useUI() {
  return useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => snapshot,
  );
}
