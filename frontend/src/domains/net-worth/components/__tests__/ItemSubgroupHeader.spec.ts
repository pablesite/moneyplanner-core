/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ItemSubgroupHeader from '../ItemSubgroupHeader.vue';

describe('ItemSubgroupHeader', () => {
  it('renders labels and totals', () => {
    const wrapper = mount(ItemSubgroupHeader, {
      props: {
        label: 'Inversiones',
        totalsLine: '600 EUR',
        baseLabel: '600 EUR',
        percent: '50',
        showBaseTotal: true,
      },
    });

    expect(wrapper.text()).toContain('Inversiones');
    expect(wrapper.text()).toContain('600 EUR');
    expect(wrapper.text()).toContain('50%');
  });

  it('hides base label when showBaseTotal is false', () => {
    const wrapper = mount(ItemSubgroupHeader, {
      props: {
        label: 'Efectivo',
        totalsLine: '300 EUR',
        baseLabel: '300 EUR',
        percent: '20',
        showBaseTotal: false,
      },
    });

    expect(wrapper.text()).toContain('300 EUR');
    expect(wrapper.text()).not.toContain('20%');
  });
});
