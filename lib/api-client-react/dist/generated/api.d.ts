import type { QueryKey, UseMutationOptions, UseMutationResult, UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import type { AnalysisServiceStatus, BrokerStatus, HealthStatus, MarketDataIngestionResponse, Mt5DemoMarketDataInput, ServiceError } from './api.schemas';
import { customFetch } from '../custom-fetch';
import type { ErrorType, BodyType } from '../custom-fetch';
type AwaitedInput<T> = PromiseLike<T> | T;
type Awaited<O> = O extends AwaitedInput<infer T> ? T : never;
type SecondParameter<T extends (...args: never) => unknown> = Parameters<T>[1];
export declare const getHealthCheckUrl: () => string;
/**
 * Returns server health status
 * @summary Health check
 */
export declare const healthCheck: (options?: Parameters<typeof customFetch>[1]) => Promise<HealthStatus>;
export declare const getHealthCheckQueryKey: () => readonly ["/api/healthz"];
export declare const getHealthCheckQueryOptions: <TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData> & {
    queryKey: QueryKey;
};
export type HealthCheckQueryResult = NonNullable<Awaited<ReturnType<typeof healthCheck>>>;
export type HealthCheckQueryError = ErrorType<unknown>;
/**
 * @summary Health check
 */
export declare function useHealthCheck<TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetBrokerStatusUrl: () => string;
/**
 * Returns DEMO, disconnected, analysis-only bridge status.
 * @summary Return the safe broker bridge status
 */
export declare const getBrokerStatus: (options?: Parameters<typeof customFetch>[1]) => Promise<BrokerStatus>;
export declare const getGetBrokerStatusQueryKey: () => readonly ["/api/broker/status"];
export declare const getGetBrokerStatusQueryOptions: <TData = Awaited<ReturnType<typeof getBrokerStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBrokerStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getBrokerStatus>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetBrokerStatusQueryResult = NonNullable<Awaited<ReturnType<typeof getBrokerStatus>>>;
export type GetBrokerStatusQueryError = ErrorType<unknown>;
/**
 * @summary Return the safe broker bridge status
 */
export declare function useGetBrokerStatus<TData = Awaited<ReturnType<typeof getBrokerStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBrokerStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getIngestMt5DemoMarketDataUrl: () => string;
/**
 * Accepts only a signed quote and exactly 100 M5 OHLCV candles. Requires HTTPS, X-Bridge-Timestamp, X-Bridge-Signature, and the server-side MT5_MARKET_DATA_BRIDGE_SECRET. The signature is HMAC-SHA256 over "<timestamp>.<exact request body bytes>". This endpoint cannot access account data or execute orders.
 * @summary Ingest authenticated XAUUSDm demo market data
 */
export declare const ingestMt5DemoMarketData: (mt5DemoMarketDataInput: Mt5DemoMarketDataInput, options?: Parameters<typeof customFetch>[1]) => Promise<MarketDataIngestionResponse>;
export declare const getIngestMt5DemoMarketDataMutationKey: () => readonly ["ingestMt5DemoMarketData"];
export declare const getIngestMt5DemoMarketDataMutationOptions: <TError = ErrorType<ServiceError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof ingestMt5DemoMarketData>>, TError, IngestMt5DemoMarketDataMutationVariables, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof ingestMt5DemoMarketData>>, TError, IngestMt5DemoMarketDataMutationVariables, TContext>;
export type IngestMt5DemoMarketDataMutationResult = NonNullable<Awaited<ReturnType<typeof ingestMt5DemoMarketData>>>;
export type IngestMt5DemoMarketDataMutationBody = BodyType<Mt5DemoMarketDataInput>;
export type IngestMt5DemoMarketDataMutationError = ErrorType<ServiceError>;
export type IngestMt5DemoMarketDataMutationVariables = {
    data: BodyType<Mt5DemoMarketDataInput>;
};
/**
* @summary Ingest authenticated XAUUSDm demo market data
*/
export declare const useIngestMt5DemoMarketData: <TError = ErrorType<ServiceError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof ingestMt5DemoMarketData>>, TError, IngestMt5DemoMarketDataMutationVariables, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof ingestMt5DemoMarketData>>, TError, IngestMt5DemoMarketDataMutationVariables, TContext>;
export declare const getGetAnalysisServiceStatusUrl: () => string;
/**
 * Returns analysis-service state and the latest analysis snapshot.
 * @summary Get analysis service status
 */
export declare const getAnalysisServiceStatus: (options?: Parameters<typeof customFetch>[1]) => Promise<AnalysisServiceStatus>;
export declare const getGetAnalysisServiceStatusQueryKey: () => readonly ["/api/analysis/service"];
export declare const getGetAnalysisServiceStatusQueryOptions: <TData = Awaited<ReturnType<typeof getAnalysisServiceStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getAnalysisServiceStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getAnalysisServiceStatus>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetAnalysisServiceStatusQueryResult = NonNullable<Awaited<ReturnType<typeof getAnalysisServiceStatus>>>;
export type GetAnalysisServiceStatusQueryError = ErrorType<unknown>;
/**
 * @summary Get analysis service status
 */
export declare function useGetAnalysisServiceStatus<TData = Awaited<ReturnType<typeof getAnalysisServiceStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getAnalysisServiceStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getStartAnalysisServiceUrl: () => string;
/**
 * Starts the analysis worker only; it cannot access broker orders.
 * @summary Start analysis-only processing
 */
export declare const startAnalysisService: (options?: Parameters<typeof customFetch>[1]) => Promise<AnalysisServiceStatus>;
export declare const getStartAnalysisServiceMutationKey: () => readonly ["startAnalysisService"];
export declare const getStartAnalysisServiceMutationOptions: <TError = ErrorType<ServiceError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof startAnalysisService>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof startAnalysisService>>, TError, void, TContext>;
export type StartAnalysisServiceMutationResult = NonNullable<Awaited<ReturnType<typeof startAnalysisService>>>;
export type StartAnalysisServiceMutationError = ErrorType<ServiceError>;
/**
* @summary Start analysis-only processing
*/
export declare const useStartAnalysisService: <TError = ErrorType<ServiceError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof startAnalysisService>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof startAnalysisService>>, TError, void, TContext>;
export declare const getStopAnalysisServiceUrl: () => string;
/**
 * Stops analysis processing; it does not interact with brokers.
 * @summary Stop analysis-only processing
 */
export declare const stopAnalysisService: (options?: Parameters<typeof customFetch>[1]) => Promise<AnalysisServiceStatus>;
export declare const getStopAnalysisServiceMutationKey: () => readonly ["stopAnalysisService"];
export declare const getStopAnalysisServiceMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof stopAnalysisService>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof stopAnalysisService>>, TError, void, TContext>;
export type StopAnalysisServiceMutationResult = NonNullable<Awaited<ReturnType<typeof stopAnalysisService>>>;
export type StopAnalysisServiceMutationError = ErrorType<unknown>;
/**
* @summary Stop analysis-only processing
*/
export declare const useStopAnalysisService: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof stopAnalysisService>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof stopAnalysisService>>, TError, void, TContext>;
export {};
//# sourceMappingURL=api.d.ts.map